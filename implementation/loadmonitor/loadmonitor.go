package loadmonitor

import (
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

/*
========================================================================================
 LOAD-AWARE QUIC INSTANT ACK: HYSTERESIS CONTROLLER (v1 BASELINE)
========================================================================================

 1. RESEARCH BACKGROUND & PROBLEM STATEMENT:
    In modern CDN edge deployments (Cloudflare, Akamai, Fastly), edge servers terminate
    QUIC connections while cryptographic credentials (TLS certs) or private keys are
    fetched from centralized Keyless SSL vaults or require slow crypto signing (Delta t).

    The IMC 2024 paper ("ReACKed QUICer") observed that the standard QUIC practice of
    Wait-for-Certificate (WFC) inflates the client's initial Probe Timeout (PTO):
        PTO_WFC = 3 * (RTT_network + Delta t)
    When packet loss occurs, the client waits through an inflated timer before retransmitting.

    The paper proposed "Instant ACK" (IACK): the server immediately transmits an
    Initial[ACK] upon ClientHello arrival, allowing the client to measure true RTT:
        PTO_IACK = 3 * RTT_network (15-20ms faster handshake)

 2. THE BOTTLENECK OF STATIC IACK UNDER CONCURRENCY:
    Under heavy concurrent client load, static IACK degrades severely:
    a) Packet Doubling: Emits 2 UDP datagrams per handshake (Initial[ACK] + Handshake[Crypto])
       instead of 1 coalesced datagram, doubling kernel `sendmsg` syscalls and context switches.
    b) Spurious PTO Storms: If server queueing causes effective certificate delay to exceed
       the client's tight PTO (Delta t_effective > 3 * RTT), the client's timer fires prematurely,
       flooding the server with redundant PTO probe packets.

 3. OUR SOLUTION: CLOSED-LOOP SCHMITT-TRIGGER HYSTERESIS:
    Instead of static policies, this module implements a bistable hysteresis controller.
    It tracks the number of currently active, in-flight handshakes (H_active) and switches:
      - Low Load (H_active <= LowThreshold, e.g. 4):  Deploy IACK for minimum latency.
      - High Load (H_active >= HighThreshold, e.g. 8): Fallback to WFC to coalesce packets,
        protect UDP socket buffers, and prevent spurious PTO probe storms.
      - Deadband (LowThreshold < H_active < HighThreshold): Maintain current state.
        This deadband mathematically prevents "mode-flapping" (chattering / limit cycles)
        that would otherwise occur if a single threshold were used with stochastic traffic.
========================================================================================
*/

// PolicyState represents the current operating strategy
type PolicyState string

const (
	// StateIACK instructs the server to send an Instant ACK immediately upon Initial packet arrival.
	// Optimizes client RTT measurement and loss detection when server capacity is available.
	StateIACK PolicyState = "IACK"

	// StateWFC instructs the server to delay and coalesce the ACK with the Certificate (Wait-for-Certificate).
	// Reduces kernel syscalls by 50% and protects against client timer expirations during high load.
	StateWFC PolicyState = "WFC"
)

// Config configures the baseline Load-Aware hysteresis thresholds (v1)
type Config struct {
	// HighHandshakeThreshold: Active handshakes >= High switches policy to WFC (Contention Protection).
	// Empirically tuned to 8 for the presentation baseline.
	HighHandshakeThreshold int64

	// LowHandshakeThreshold: Active handshakes <= Low switches policy to IACK (Headroom Available).
	// Empirically tuned to 4 for the presentation baseline.
	LowHandshakeThreshold int64

	// SamplingInterval: Metrics snapshot interval for background reporting.
	SamplingInterval time.Duration
}

// Stats holds an atomic snapshot of server contention and decision metrics
type Stats struct {
	ActiveHandshakes int64       `json:"active_handshakes"` // Number of handshakes currently in-flight
	PeakHandshakes   int64       `json:"peak_handshakes"`   // Highest concurrent handshakes seen
	TotalStarted     int64       `json:"total_started"`     // Cumulative handshakes initiated
	TotalCompleted   int64       `json:"total_completed"`   // Cumulative handshakes successfully finished
	TotalFailed      int64       `json:"total_failed"`      // Cumulative handshakes timed out / failed
	IACKDecisions    int64       `json:"iack_decisions"`    // Count of Instant ACK emissions
	WFCDecisions     int64       `json:"wfc_decisions"`     // Count of Coalesced WFC decisions
	CurrentState     PolicyState `json:"current_state"`     // Active operating state (IACK or WFC)
}

// LoadMonitor is the Core v1 Load-Aware Decision Engine.
// It tracks active handshake concurrency and applies a Schmitt-trigger hysteresis controller.
type LoadMonitor struct {
	cfg Config

	// Atomic counters for lock-free concurrency tracking (<10ns overhead on packet arrival)
	activeHandshakes atomic.Int64
	peakHandshakes   atomic.Int64
	totalStarted     atomic.Int64
	totalCompleted   atomic.Int64
	totalFailed      atomic.Int64
	iackDecisions    atomic.Int64
	wfcDecisions     atomic.Int64

	// Mutex protecting the hysteresis state transitions
	mu           sync.RWMutex
	currentState PolicyState
}

// NewLoadMonitor initializes the v1 LoadMonitor with verified default hysteresis thresholds [4, 8]
func NewLoadMonitor(cfg Config) *LoadMonitor {
	if cfg.HighHandshakeThreshold <= 0 {
		cfg.HighHandshakeThreshold = 8 // Default high threshold
	}
	if cfg.LowHandshakeThreshold <= 0 {
		cfg.LowHandshakeThreshold = 4 // Default low threshold
	}
	// Sanity check: ensure low threshold is strictly less than high threshold to form a deadband
	if cfg.LowHandshakeThreshold >= cfg.HighHandshakeThreshold {
		cfg.LowHandshakeThreshold = cfg.HighHandshakeThreshold / 2
	}
	if cfg.SamplingInterval <= 0 {
		cfg.SamplingInterval = 50 * time.Millisecond
	}

	return &LoadMonitor{
		cfg:          cfg,
		currentState: StateIACK, // Start optimistically in IACK for minimum cold-start latency
	}
}

// OnHandshakeStart is hooked into connection.go and fires when an incoming client Initial packet arrives.
// It executes in O(1) time using atomic operations to avoid stalling the incoming packet handler.
func (m *LoadMonitor) OnHandshakeStart() {
	active := m.activeHandshakes.Add(1)
	m.totalStarted.Add(1)

	// Update peak tracking lock-free using atomic Compare-And-Swap (CAS)
	for {
		peak := m.peakHandshakes.Load()
		if active <= peak || m.peakHandshakes.CompareAndSwap(peak, active) {
			break
		}
	}
}

// OnHandshakeComplete is hooked into connection.go and fires when a handshake finishes or aborts.
// Atomically decrements the active handshake counter to reflect newly available server capacity.
func (m *LoadMonitor) OnHandshakeComplete(success bool) {
	m.activeHandshakes.Add(-1)
	if success {
		m.totalCompleted.Add(1)
	} else {
		m.totalFailed.Add(1)
	}
}

// ShouldSendInstantACK evaluates server contention and applies the Schmitt-trigger hysteresis logic:
//
//   1. High Threshold Check (active >= HighThreshold):
//      Server contention is detected. Transition to WFC. Halves the packet flight count,
//      preventing socket queue saturation and shielding clients from premature PTO expiration.
//
//   2. Low Threshold Check (active <= LowThreshold):
//      Sufficient server headroom exists. Transition to IACK. Enables immediate RTT sampling
//      for optimal 1-RTT handshake completion speed.
//
//   3. Hysteresis Deadband (LowThreshold < active < HighThreshold):
//      The controller maintains its current state without modification.
//      This deadband absorbs high-frequency stochastic variations in client arrivals,
//      preventing destructive mode-flapping (limit-cycle oscillation).
func (m *LoadMonitor) ShouldSendInstantACK() bool {
	// Read atomic counter without acquiring mutex
	active := m.activeHandshakes.Load()

	m.mu.Lock()
	defer m.mu.Unlock()

	// Step 1: Evaluate High Threshold Barrier (Contention Protection)
	if active >= m.cfg.HighHandshakeThreshold {
		m.currentState = StateWFC
	} else if active <= m.cfg.LowHandshakeThreshold {
		// Step 2: Evaluate Low Threshold Barrier (Headroom Available)
		m.currentState = StateIACK
	}
	// Step 3: Deadband: If between Low (4) and High (8), preserve currentState unchanged!

	// Apply policy decision and record telemetry
	if m.currentState == StateIACK {
		m.iackDecisions.Add(1)
		return true // Send Initial ACK immediately
	}

	m.wfcDecisions.Add(1)
	return false // Coalesce ACK with Certificate later (WFC)
}

// GetStats returns a snapshot of current metrics for the HTTP /stats telemetry endpoint
func (m *LoadMonitor) GetStats() Stats {
	m.mu.RLock()
	state := m.currentState
	m.mu.RUnlock()

	return Stats{
		ActiveHandshakes: m.activeHandshakes.Load(),
		PeakHandshakes:   m.peakHandshakes.Load(),
		TotalStarted:     m.totalStarted.Load(),
		TotalCompleted:   m.totalCompleted.Load(),
		TotalFailed:      m.totalFailed.Load(),
		IACKDecisions:    m.iackDecisions.Load(),
		WFCDecisions:     m.wfcDecisions.Load(),
		CurrentState:     state,
	}
}

// String returns human-readable status for console telemetry and debug logging
func (m *LoadMonitor) String() string {
	s := m.GetStats()
	return fmt.Sprintf("[v1-Classic] Active: %d, Peak: %d, Started: %d, Completed: %d, IACK: %d, WFC: %d, Mode: %s",
		s.ActiveHandshakes, s.PeakHandshakes, s.TotalStarted, s.TotalCompleted, s.IACKDecisions, s.WFCDecisions, s.CurrentState)
}
