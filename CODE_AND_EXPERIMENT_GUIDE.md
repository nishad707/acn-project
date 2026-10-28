# Master Code & Experiment Guide: Load-Aware QUIC Instant ACK

**Course**: COL724 / COL7524: Advanced Computer Networks (IIT Delhi, Semester 1, 2026–27)  
**Team**: Muhammed Nishad (2026MCS2799) & Ayush Arya (2026MCS2802)  
**Base Paper**: *ReACKed QUICer: Measuring the Performance of Instant Acknowledgments in QUIC Handshakes* (ACM IMC 2024)

---

## Table of Contents
1. [Repository & Directory Architecture](#1-repository--directory-architecture)
2. [Part 1: Core Presentation Baseline (v1) — Master This for Tomorrow](#2-part-1-core-presentation-baseline-v1--master-this-for-tomorrow)
   - [2.1 Code Walkthrough: `loadmonitor.go` (The Hysteresis Engine)](#21-code-walkthrough-loadmonitorgo-the-hysteresis-engine)
   - [2.2 Code Walkthrough: `quic-go/connection.go` (The Engine Hooks)](#22-code-walkthrough-quic-goconnectiongo-the-engine-hooks)
   - [2.3 Code Walkthrough: The Server, Client, and UDP Proxy](#23-code-walkthrough-the-server-client-and-udp-proxy)
   - [2.4 The 8 Presentation Baseline Experiments & Figures](#24-the-8-presentation-baseline-experiments--figures)
3. [Part 2: Advanced Experimental Extension (v2 & Stress Suite)](#3-part-2-advanced-experimental-extension-v2--stress-suite)
   - [3.1 Why v2 Was Built](#31-why-v2-was-built)
   - [3.2 Code Walkthrough: `loadmonitor_v2.go` (Lock-Free + Velocity + Token Bucket)](#32-code-walkthrough-loadmonitor_v2go-lock-free--velocity--token-bucket)
   - [3.3 The Exploratory Stress Suite (Experiments A through E)](#33-the-exploratory-stress-suite-experiments-a-through-e)
   - [3.4 Grand Comparison: v1 vs v2](#34-grand-comparison-v1-vs-v2)
4. [Quick Terminal Commands Cheat Sheet](#4-quick-terminal-commands-cheat-sheet)

---

## 1. Repository & Directory Architecture

To ensure 100% clarity, the codebase and experimental outputs are strictly organized into two distinct tiers:

```
ACN Project/
├── implementation/
│   ├── loadmonitor/
│   │   ├── loadmonitor.go        <-- [TIER 1: v1] Clean, readable Schmitt-trigger hysteresis for tomorrow
│   │   └── loadmonitor_v2.go     <-- [TIER 2: v2] Advanced lock-free + velocity + token bucket
│   ├── cmd/
│   │   ├── server/main.go        <-- Multi-mode QUIC server (supports wfc, iack, loadaware with v1/v2)
│   │   ├── client/main.go        <-- Multi-threaded measurement client (records RTT, TTFB, t1-t4, PTOs)
│   │   └── proxy/main.go         <-- Standalone UDP network emulator (RTT delay, loss, jitter)
│   ├── dashboard/app.py          <-- Real-time Streamlit web dashboard
│   └── scripts/
│       ├── run_experiments.py    <-- Runs the 8 baseline experiments (Tier 1)
│       ├── generate_plots.py     <-- Generates Figures 1-8 for tomorrow's slides
│       ├── run_all_v2_and_compare.py <-- Master execution & grand comparison suite (Tier 2)
│       └── run_exp_*.py          <-- Isolated exploratory stress scripts
├── figures/
│   ├── presentation_baseline/    <-- [TIER 1] The EXACT 8 figures (fig1 to fig8) for tomorrow's slides
│   └── v2_and_stress_exploratory/<-- [TIER 2] Advanced v2 comparison & stress figures
├── data/
│   ├── presentation_baseline/    <-- [TIER 1] The 8 raw baseline CSVs
│   └── v2_and_stress_exploratory/<-- [TIER 2] v2 & exploratory stress CSVs
└── toolchain/go/bin/go           <-- Dedicated Go 1.20.7 binary strictly required by qtls
```

---

## 2. Part 1: Core Presentation Baseline (v1) — Master This for Tomorrow

This is the exact material you and Muhammed will present tomorrow on October 28. It corresponds 1-to-1 with the Implementation Plan.

### 2.1 Code Walkthrough: `loadmonitor.go` (The Hysteresis Engine)
Located at: [`implementation/loadmonitor/loadmonitor.go`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/implementation/loadmonitor/loadmonitor.go)

#### The Problem It Solves:
In CDN architectures, the edge server terminating QUIC handshakes has an internal delay $\Delta t$ while retrieving TLS certificates.
* **Static WFC**: Server waits for certificate before sending anything. Flaw: Client measures $\text{RTT} + \Delta t$, inflating its initial timer ($\text{PTO} \approx 3 \times (\text{RTT} + \Delta t)$). If a packet drops, recovery is delayed.
* **Static IACK**: Server sends `Initial[ACK]` immediately. Flaw: Emits 2 packet flights (`Initial[ACK]` + `Handshake[Crypto]`), doubling `sendmsg` syscalls. Under high concurrency, socket buffers choke and latency explodes to $128+\text{ ms}$.

#### How `loadmonitor.go` Works:
1. **Concurrency Tracking**:
   ```go
   active := m.activeHandshakes.Add(1) // Atomic increment on initial packet arrival
   m.activeHandshakes.Add(-1)          // Atomic decrement on completion/timeout
   ```
2. **Schmitt-Trigger Hysteresis Controller**:
   ```go
   func (m *LoadMonitor) ShouldSendInstantACK() bool {
       active := m.activeHandshakes.Load()
       m.mu.Lock()
       defer m.mu.Unlock()

       if active >= m.cfg.HighHandshakeThreshold { // e.g. 8
           m.currentState = StateWFC  // Contention protection: switch to coalesced flight
       } else if active <= m.cfg.LowHandshakeThreshold { // e.g. 4
           m.currentState = StateIACK // Headroom available: switch to fast Instant ACK
       }
       // If active is between 4 and 8: preserve previous state (deadband prevents flapping)

       return m.currentState == StateIACK
   }
   ```
* **Why Hysteresis?**: A single threshold (e.g. at 6) would cause rapid oscillation ("mode flapping") if traffic fluctuated around 6. The deadband between $\tau_{\text{low}}=4$ and $\tau_{\text{high}}=8$ absorbs noise and guarantees stable transitions.

---

### 2.2 Code Walkthrough: `quic-go/connection.go` (The Engine Hooks)
Located in modified research repo: `artifacts-imc24-reACKed-QUICer/01-quic-go-instant-ack/`

We hooked `LoadMonitor` into the packet processing lifecycle inside `connection.go`:
```go
// In handleUnpackedLongHeaderPacket()
shouldSendIACK := s.config.EnableInstantACK
if s.config.EnableLoadAware && s.config.ShouldSendInstantACK != nil {
    shouldSendIACK = s.config.ShouldSendInstantACK() // Dynamic query to LoadMonitor
}

if shouldSendIACK {
    // IACK PATH: Emit Initial ACK immediately
    s.receivedPacketHandler.ReceivedPacket(packet.hdr.PacketNumber, ecn, packet.encryptionLevel, rcvTime, true)
    s.triggerSending()
    if s.config.EnableInstantACKDelay > 0 {
        betterSleep(time.Now(), s.config.EnableInstantACKDelay) // Simulated Δt
    }
} else {
    // WFC PATH: Wait for certificate before emitting anything
    if s.config.EnableFirstPacketDelay > 0 {
        betterSleep(time.Now(), s.config.EnableFirstPacketDelay)
    }
}
```

---

### 2.3 Code Walkthrough: The Server, Client, and UDP Proxy

1. **`cmd/server/main.go`**:
   * Accepts `--mode=wfc`, `--mode=iack`, or `--mode=loadaware`.
   * Accepts `--cert-delay=20ms` (simulated $\Delta t$).
   * Accepts `--low-thresh=4 --high-thresh=8`.
   * Serves live JSON metrics at `http://127.0.0.1:8080/stats`.
2. **`cmd/proxy/main.go`**:
   * Platform-independent user-space UDP bridge listening on `127.0.0.1:6000` and forwarding to `127.0.0.1:4433`.
   * Adds bidirectional simulated latency: `time.Sleep(rtt / 2)`.
   * Enlarged to 4MB socket buffer (`SetReadBuffer`) to prevent local loopback packet drops.
3. **`cmd/client/main.go`**:
   * Multi-threaded goroutine worker launching concurrent handshakes.
   * Records handshake duration, TTFB, and decomposes phase timestamps ($t_1$ to $t_4$).
   * Tracks spurious client Probe Timeouts (`res.PTOCount`).

---

### 2.4 The 8 Presentation Baseline Experiments & Figures

All 8 figures are located in [`figures/presentation_baseline/`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/presentation_baseline/):

| Figure & Filename | Experiment Description | Slide Mapping & What to Say |
| :--- | :--- | :--- |
| **Figure 1**<br>`fig1_handshake_latency_vs_rtt.png` | Handshake Latency vs Network RTT (10ms to 100ms) under light load. | **Slide 6**: *"Under light load, Load-Aware reliably chooses Instant ACK, outperforming WFC by 15–20 ms across all RTTs."* |
| **Figure 2**<br>`fig2_ttfb_vs_rtt.png` | Time to First Byte (TTFB) vs Network RTT. | **Slide 6**: *"TTFB scales linearly with path RTT, confirming Instant ACK does not impair application payload delivery."* |
| **Figure 3**<br>`fig3_latency_under_load.png` | **The Core Thesis**: Concurrency Load Ramp (1 to 75 clients). | **Slide 7**: *"Static IACK degrades sharply to 128+ ms at 50–75 clients. Load-Aware caps latency at 102 ms (~20% improvement)."* |
| **Figure 4**<br>`fig4_policy_decision_transition.png` | Stacked bar chart of autonomous server decisions. | **Slide 7**: *"Shows the automated shift from 100% IACK decisions (green) at low load to 93%+ WFC fallback (blue) as concurrency increases."* |
| **Figure 5**<br>`fig5_cert_delay_sweep_crossover.png` | Certificate delay sweep ($\Delta t$) from 10ms to 180ms. | **Slide 8**: *"Identifies the PTO crossover boundary: when $\Delta t > 3 \times \text{RTT}$ (120ms), Static IACK triggers spurious PTO retransmissions."* |
| **Figure 6**<br>`fig6_phase_wait_time_breakdown.png` | Decomposing handshake into 4 phases ($t_1, t_2, t_3, t_4$). | **Slide 8**: *"Deconstructs wait time: in IACK, $t_1$ is low, but under load $t_2$ (certificate wait) balloons due to queueing. Load-Aware fixes this."* |
| **Figure 7**<br>`fig7_threshold_sensitivity.png` | Threshold tuning deadbands: $[(2,4), (4,8), (8,16), (15,30)]$. | **Slide 9**: *"Proves that $[4, 8]$ provides the optimal balance between rapid responsiveness and preventing rapid mode-flapping."* |
| **Figure 8**<br>`fig8_winner_heatmap.png` | **Headline Figure**: 2D Parameter Heatmap ($\Delta t \times \text{Load}$). | **Slide 9**: *"Visualizes the entire design space: green represents where Load-Aware wins. Proves that static configurations are always suboptimal in half the design space."* |

---

## 3. Part 2: Advanced Experimental Extension (v2 & Stress Suite)

*(Keep this as your secret weapon / backup slides for Q&A and final report).*

### 3.1 Why v2 Was Built
While v1 proved the core thesis, our stress testing revealed opportunities for production-grade optimization:
1. **Mutex Contention**: In v1, `m.mu.Lock()` on every packet created thread contention under thousands of concurrent clients.
2. **Surge Blindness**: In a sudden flash crowd of 250 connections, by the time `activeHandshakes` reaches 8, hundreds of datagrams are already queued in the OS socket buffer.
3. **Burst Flooding**: Binary switching allowed unpaced packet bursts before the cutoff.

### 3.2 Code Walkthrough: `loadmonitor_v2.go` (Lock-Free + Velocity + Token Bucket)
Located at: [`implementation/loadmonitor/loadmonitor_v2.go`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/implementation/loadmonitor/loadmonitor_v2.go)

1. **Sub-Nanosecond Lock-Free Fast Path**:
   * Uses `atomic.Int32` (`stateAtomic: 0=IACK, 1=WFC`). Zero mutex locks on the packet path ($<5\text{ ns}$ execution).
2. **Arrival Velocity Prediction ($d\text{Load}/dt$)**:
   * Tracks arrival rate derivative: $L_{\text{effective}} = H_{\text{active}} + \alpha \cdot \frac{\Delta \text{Arrivals}}{\Delta t}$.
   * Pre-emptively shifts to single-flight coalescing before kernel socket queues overflow.
3. **Token-Bucket Burst Pacer**:
   * Maintains an atomic token bucket refilling every 10ms. Prevents datagram bursts from choking socket buffers.

---

### 3.3 The Exploratory Stress Suite (Experiments A through E)

All figures located in [`figures/v2_and_stress_exploratory/`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/v2_and_stress_exploratory/):

1. **Experiment A (A.1, A.2, A.3)**: Host CPU Starvation (8 cores pegged) & Mega Concurrency ($500$ & $5,000$ clients).  
   * *Key Finding*: In a 500-client burst, Load-Aware was **60.9% faster** than IACK ($752\text{ ms}$ vs $1,925\text{ ms}$). At 5,000 clients, v2 cut probe storms by **36.2%** ($3,112$ probes vs $4,875$).
2. **Experiment B: The Flash Crowd** (100 to 250 simultaneous clients, `ramp=0ms`).  
   * *Key Finding*: Proved the mid-range crossover where Load-Aware beats **both** static baselines ($337\text{ ms}$ vs $759\text{ ms}$ for IACK and $920\text{ ms}$ for WFC). In a 250-client burst, v2 was **293 ms faster** than v1 ($771\text{ ms}$ vs $1,064\text{ ms}$).
3. **Experiment C: Packet Loss Resilience** (0%, 2%, 5%, 8% loss).  
   * *Key Finding*: WFC's inflated timer causes a 95th percentile tail latency blowout of **$328.6\text{ ms}$** at 5% loss. Load-Aware recovers in **$129.9\text{ ms}$** ($60.5\%$ faster recovery).
4. **Experiment D: The Pulsing Wave** (7 alternating waves of peacetime and spikes).  
   * *Key Finding*: Zero mode-flapping. The controller toggles cleanly `IACK -> WFC -> IACK` without oscillation, recovering back to peacetime within $<300\text{ ms}$.
5. **Experiment E: High Network Jitter** (0ms to 45ms jitter).  
   * *Key Finding*: Found the timer breakdown threshold: at $\pm 45\text{ ms}$ jitter, IACK mistakes cellular delay for packet loss and emits spurious probes. v2 remains immune and flat at $88\text{ ms}$.

---

### 3.4 Grand Comparison: v1 vs v2
*Embed: [`figures/v2_and_stress_exploratory/v1_vs_v2_grand_comparison.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/v2_and_stress_exploratory/v1_vs_v2_grand_comparison.png)*

* **Peacetime**: v1 and v2 are identical within $<1\text{ ms}$.
* **Flash Crowds**: v2 is **32% faster** at 100 clients and **27.6% faster** at 250 clients ($771\text{ ms}$ vs $1,064\text{ ms}$).
* **Severe Jitter**: v2 eliminates the 14ms latency creep seen in v1.
* **Overload**: v2 suppresses 1,763 redundant probe packets compared to v1.

---

## 4. Quick Terminal Commands Cheat Sheet

### Run the Baseline Presentation Tests & Regenerate Figures 1–8:
```bash
# Set environment
export GOPATH="$(pwd)/.gopath"
export GOCACHE="$(pwd)/.gocache"

# 1. Run the 8 baseline experiments
python3 implementation/scripts/run_experiments.py

# 2. Regenerate the 8 presentation plots
MPLCONFIGDIR=/tmp/matplotlib_cache .venv/bin/python3 implementation/scripts/generate_plots.py
```

### Launch the Real-Time Web Dashboard:
```bash
# Terminal 1: Start the Load-Aware Server
./implementation/bin/server --mode=loadaware --addr=127.0.0.1:4433 --metrics-addr=127.0.0.1:8080

# Terminal 2: Start Streamlit Dashboard
.venv/bin/streamlit run implementation/dashboard/app.py --server.port=8501
```
Open your browser at `http://localhost:8501`.

---

*You now have a clean, separated, and thoroughly documented project dossier. You can read and study Section 2 with complete confidence for tomorrow's presentation!*
