package main

import (
	"context"
	"crypto/tls"
	"flag"
	"fmt"
	"io"
	"log"
	"sync"
	"time"

	"github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/logging"
)

/*
========================================================================================
 MULTI-THREADED QUIC MEASUREMENT CLIENT & TELEMETRY PROFILER
========================================================================================

 This client measures connection setup dynamics and protocol timing breakdown:
   1. Handshake Time: From initial ClientHello transmission to HANDSHAKE_DONE.
   2. Time to First Byte (TTFB): From HTTP/3 request stream write to first payload byte.
   3. Phase Breakdown (t1 through t4):
      - t1: ClientHello to reception of First Server Packet (Instant ACK in IACK mode,
            or Coalesced Cert Flight in WFC mode).
      - t2: Time spent waiting between First Server Packet and Certificate Flight (Delta t).
      - t3: Certificate Flight processing to Handshake completion.
      - t4: Handshake completion to first application stream data byte.
   4. Spurious PTO Count: Intercepts RFC 9002 loss detection timers via ConnectionTracer
      to detect when client probe timeouts expire prematurely.
========================================================================================
*/

// ConnectionResult holds detailed timing telemetry for an individual connection
type ConnectionResult struct {
	WorkerID      int           `json:"worker_id"`
	HandshakeTime time.Duration `json:"handshake_time_ms"`
	TTFB          time.Duration `json:"ttfb_ms"`
	TotalDuration time.Duration `json:"total_duration_ms"`
	T1            time.Duration `json:"t1_ms"` // Phase 1: ClientHello -> First Server Packet
	T2            time.Duration `json:"t2_ms"` // Phase 2: First Server Packet -> Cert Flight (Delta t)
	T3            time.Duration `json:"t3_ms"` // Phase 3: Cert Flight -> Handshake Complete
	T4            time.Duration `json:"t4_ms"` // Phase 4: Handshake Complete -> TTFB
	PTOCount      uint32        `json:"pto_count"` // Number of RFC 9002 Probe Timeouts triggered
	BytesReceived int           `json:"bytes_received"`
	Success       bool          `json:"success"`
	Error         string        `json:"error,omitempty"`
}

// runSingleConnection establishes a QUIC connection, tracks packet timestamps via Tracer,
// performs a 10KB application request, and computes latency metrics.
func runSingleConnection(ctx context.Context, workerID int, target string, tlsConfig *tls.Config) ConnectionResult {
	res := ConnectionResult{WorkerID: workerID}

	var mu sync.Mutex
	var tFirstPacket, tCertPacket time.Time
	var ptoCount uint32

	// ConnectionTracer attaches to the QUIC event loop without altering cryptographic state
	tracer := &logging.ConnectionTracer{
		// Intercept incoming long-header packets to record arrival times for phase breakdown
		ReceivedLongHeaderPacket: func(hdr *logging.ExtendedHeader, size logging.ByteCount, ecn logging.ECN, frames []logging.Frame) {
			mu.Lock()
			defer mu.Unlock()
			if tFirstPacket.IsZero() {
				tFirstPacket = time.Now() // Marks arrival of Packet 1 (Instant ACK or WFC packet)
			} else if tCertPacket.IsZero() {
				tCertPacket = time.Now()  // Marks arrival of Packet 2 (Delayed Cert Flight)
			}
		},
		// Intercept RFC 9002 PTO timer expirations
		UpdatedPTOCount: func(val uint32) {
			mu.Lock()
			if val > ptoCount {
				ptoCount = val // Records if client fired probe packets due to timer expiration
			}
			mu.Unlock()
		},
	}

	quicConfig := &quic.Config{
		HandshakeIdleTimeout: 5 * time.Second,
		MaxIdleTimeout:       10 * time.Second,
		Tracer: func(context.Context, logging.Perspective, quic.ConnectionID) *logging.ConnectionTracer {
			return tracer
		},
	}

	t0 := time.Now()
	// Initiate QUIC 1-RTT Handshake
	conn, err := quic.DialAddr(ctx, target, tlsConfig, quicConfig)
	if err != nil {
		res.Error = err.Error()
		res.TotalDuration = time.Since(t0)
		return res
	}
	defer conn.CloseWithError(0, "client done")

	tHandshakeDone := time.Now()
	res.HandshakeTime = tHandshakeDone.Sub(t0)

	// Calculate phase breakdowns (t1, t2, t3)
	mu.Lock()
	res.PTOCount = ptoCount
	if !tFirstPacket.IsZero() {
		res.T1 = tFirstPacket.Sub(t0)
		if !tCertPacket.IsZero() {
			res.T2 = tCertPacket.Sub(tFirstPacket)
			res.T3 = tHandshakeDone.Sub(tCertPacket)
		} else {
			// In WFC mode, both ACK and Certificate arrive coalesced in the first packet
			res.T2 = 0
			res.T3 = tHandshakeDone.Sub(tFirstPacket)
		}
	} else {
		res.T1 = res.HandshakeTime
	}
	mu.Unlock()

	// Open HTTP/3-style unidirectional stream to fetch payload
	stream, err := conn.OpenStreamSync(ctx)
	if err != nil {
		res.Error = err.Error()
		res.TotalDuration = time.Since(t0)
		return res
	}
	defer stream.Close()

	tStartReq := time.Now()
	_, err = stream.Write([]byte("GET /10k"))
	if err != nil {
		res.Error = err.Error()
		res.TotalDuration = time.Since(t0)
		return res
	}

	// Read first byte to record TTFB
	buf := make([]byte, 1024)
	n, err := stream.Read(buf)
	if err != nil && err != io.EOF {
		res.Error = err.Error()
		res.TotalDuration = time.Since(t0)
		return res
	}
	tFirstByte := time.Now()
	res.TTFB = tFirstByte.Sub(tStartReq)
	res.T4 = res.TTFB
	res.BytesReceived = n

	// Read remaining payload data to complete transfer
	for {
		rn, rerr := stream.Read(buf)
		res.BytesReceived += rn
		if rerr != nil {
			break
		}
	}

	res.TotalDuration = time.Since(t0)
	res.Success = true
	return res
}

func main() {
	target := flag.String("target", "127.0.0.1:6000", "Server or proxy UDP address")
	concurrency := flag.Int("concurrency", 1, "Number of concurrent connections to launch")
	requests := flag.Int("requests", 1, "Total requests per worker")
	csvOutput := flag.Bool("csv", false, "Print results in CSV format for automated plotting")
	rampMs := flag.Int("ramp-ms", 0, "Ramp duration in ms over which workers are launched (0 for instant flash crowd)")
	timeoutSec := flag.Int("timeout", 12, "Per-connection timeout in seconds")
	flag.Parse()

	tlsConfig := &tls.Config{
		InsecureSkipVerify: true,
		NextProtos:         []string{"loadaware-quic-v1"},
	}

	if *csvOutput {
		fmt.Println("worker_id,handshake_ms,ttfb_ms,total_ms,t1_ms,t2_ms,t3_ms,t4_ms,pto_count,bytes,success,error")
	} else {
		log.Printf("[Client] Launching %d concurrent workers targeting %s (requests/worker: %d)...",
			*concurrency, *target, *requests)
	}

	var wg sync.WaitGroup
	var resultsMu sync.Mutex
	var allResults []ConnectionResult

	startAll := time.Now()

	// Calculate inter-worker launch delay if pacing is enabled
	interval := time.Duration(0)
	if *rampMs > 0 && *concurrency > 1 {
		interval = time.Duration(*rampMs*1000/ *concurrency) * time.Microsecond
	}

	// Launch concurrent worker goroutines
	for w := 0; w < *concurrency; w++ {
		if interval > 0 && w > 0 {
			time.Sleep(interval)
		}
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			for r := 0; r < *requests; r++ {
				ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*timeoutSec)*time.Second)
				res := runSingleConnection(ctx, workerID, *target, tlsConfig)
				cancel()

				resultsMu.Lock()
				allResults = append(allResults, res)
				if *csvOutput {
					fmt.Printf("%d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%d,%d,%t,%s\n",
						res.WorkerID,
						float64(res.HandshakeTime.Microseconds())/1000.0,
						float64(res.TTFB.Microseconds())/1000.0,
						float64(res.TotalDuration.Microseconds())/1000.0,
						float64(res.T1.Microseconds())/1000.0,
						float64(res.T2.Microseconds())/1000.0,
						float64(res.T3.Microseconds())/1000.0,
						float64(res.T4.Microseconds())/1000.0,
						res.PTOCount,
						res.BytesReceived,
						res.Success,
						res.Error,
					)
				}
				resultsMu.Unlock()
			}
		}(w)
	}

	wg.Wait()
	totalElapsed := time.Since(startAll)

	// Summary output when running in non-CSV interactive mode
	if !*csvOutput {
		successCount := 0
		var sumHandshake, sumTTFB time.Duration
		var totalPTO uint32
		for _, r := range allResults {
			if r.Success {
				successCount++
				sumHandshake += r.HandshakeTime
				sumTTFB += r.TTFB
				totalPTO += r.PTOCount
			}
		}

		log.Printf("[Client] Finished %d requests in %v (Success: %d/%d, Total PTO Fired: %d)",
			len(allResults), totalElapsed, successCount, len(allResults), totalPTO)
		if successCount > 0 {
			avgHandshake := sumHandshake / time.Duration(successCount)
			avgTTFB := sumTTFB / time.Duration(successCount)
			log.Printf("[Client] Avg Handshake Latency: %v | Avg TTFB: %v", avgHandshake, avgTTFB)
		}
	}
}
