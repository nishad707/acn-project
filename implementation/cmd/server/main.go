package main

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/json"
	"flag"
	"log"
	"math/big"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/quic-go/quic-go"
	"loadaware-quic/loadmonitor"
)

/*
========================================================================================
 MULTI-MODE QUIC RESEARCH SERVER (WFC vs. IACK vs. LOAD-AWARE)
========================================================================================

 This server serves as our core evaluation platform, modeling CDN edge behavior:
   1. Static WFC (--mode=wfc):
      Waits for certificate retrieval/signing (simulated by --cert-delay Delta t),
      then transmits a single coalesced packet flight (Initial[ACK] + Handshake[Crypto]).
   2. Static IACK (--mode=iack):
      Immediately transmits Initial[ACK] in flight 1, and transmits Handshake[Crypto]
      after cert-delay Delta t in flight 2.
   3. Load-Aware (--mode=loadaware):
      Dynamically chooses between IACK and WFC per incoming handshake using the
      LoadMonitor decision engine based on concurrent server load.

 Telemetry & Observability:
   - Exposes an HTTP JSON endpoint at http://<metrics-addr>/stats for real-time
     dashboard tracking (active handshakes, decision counts, mode transitions).
========================================================================================
*/

// generateTLSConfig creates an ephemeral, in-memory RSA-2048 self-signed certificate
// for authenticating QUIC TLS 1.3 handshakes in our testbed without external disk dependencies.
func generateTLSConfig() (*tls.Config, error) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, err
	}
	template := x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject: pkix.Name{
			Organization: []string{"LoadAware QUIC Testbed"},
		},
		NotBefore:             time.Now().Add(-1 * time.Hour),
		NotAfter:              time.Now().Add(24 * time.Hour),
		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		IPAddresses:           []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
		DNSNames:              []string{"localhost"},
	}
	certDER, err := x509.CreateCertificate(rand.Reader, &template, &template, &key.PublicKey, key)
	if err != nil {
		return nil, err
	}
	keyPEM := tls.Certificate{
		Certificate: [][]byte{certDER},
		PrivateKey:  key,
	}
	return &tls.Config{
		Certificates: []tls.Certificate{keyPEM},
		NextProtos:   []string{"loadaware-quic-v1"},
	}, nil
}

func main() {
	// Command-line flag parsing
	mode := flag.String("mode", "loadaware", "Operating mode: wfc (static), iack (static), loadaware (adaptive)")
	addr := flag.String("addr", "127.0.0.1:4433", "UDP address to bind the QUIC server")
	certDelay := flag.Duration("cert-delay", 20*time.Millisecond, "Backend cert fetch / crypto delay (Delta t)")
	highThresh := flag.Int64("high-thresh", 10, "Load-Aware high threshold (switch to WFC)")
	lowThresh := flag.Int64("low-thresh", 5, "Load-Aware low threshold (switch to IACK)")
	metricsAddr := flag.String("metrics-addr", "127.0.0.1:8080", "HTTP metrics listener address (/stats endpoint)")
	policyVersion := flag.String("policy-version", "v1", "Policy engine version: v1 (classic hysteresis), v2 (lock-free + velocity + token bucket)")
	flag.Parse()

	log.Printf("[Server] Starting with mode=%s, version=%s, addr=%s, certDelay=%v, thresh=[%d, %d]",
		*mode, *policyVersion, *addr, *certDelay, *lowThresh, *highThresh)

	// Function hooks injected into upstream quic-go/connection.go
	var startHook func()
	var completeHook func(bool)
	var decisionHook func() bool
	var statsHook func() any
	var stringHook func() string

	// Initialize the selected policy engine version (v1 classic or v2 lock-free)
	if *policyVersion == "v2" {
		m2 := loadmonitor.NewLoadMonitorV2(loadmonitor.ConfigV2{
			HighHandshakeThreshold: *highThresh,
			LowHandshakeThreshold:  *lowThresh,
		})
		startHook = m2.OnHandshakeStart
		completeHook = m2.OnHandshakeComplete
		decisionHook = m2.ShouldSendInstantACK
		statsHook = func() any { return m2.GetStats() }
		stringHook = m2.String
	} else {
		m1 := loadmonitor.NewLoadMonitor(loadmonitor.Config{
			HighHandshakeThreshold: *highThresh,
			LowHandshakeThreshold:  *lowThresh,
		})
		startHook = m1.OnHandshakeStart
		completeHook = m1.OnHandshakeComplete
		decisionHook = m1.ShouldSendInstantACK
		statsHook = func() any { return m1.GetStats() }
		stringHook = m1.String
	}

	// Configure QUIC Config parameters that hook directly into the IMC '24 research fork
	quicConf := &quic.Config{
		EnableFirstPacketDelay: 0,
		EnableInstantACK:       false,
		EnableInstantACKDelay:  0,
	}

	switch *mode {
	case "wfc":
		// Static Wait-for-Certificate: delay initial emission until certificate is ready
		quicConf.EnableFirstPacketDelay = *certDelay
		quicConf.EnableInstantACK = false
		log.Printf("[Server] Configured STATIC WFC mode (FirstPacketDelay=%v)", *certDelay)

	case "iack":
		// Static Instant ACK: emit standalone ACK immediately, delay cert flight by certDelay
		quicConf.EnableInstantACK = true
		quicConf.EnableInstantACKDelay = *certDelay
		log.Printf("[Server] Configured STATIC IACK mode (InstantACKDelay=%v)", *certDelay)

	case "loadaware":
		// Load-Aware Mode: dynamic decision per handshake based on server queue state
		quicConf.EnableLoadAware = true
		quicConf.EnableInstantACKDelay = *certDelay
		quicConf.EnableFirstPacketDelay = *certDelay
		quicConf.OnHandshakeStart = startHook
		quicConf.OnHandshakeComplete = completeHook
		quicConf.ShouldSendInstantACK = decisionHook
		log.Printf("[Server] Configured LOAD-AWARE mode (Version=%s, Thresholds: low=%d, high=%d)", *policyVersion, *lowThresh, *highThresh)

	default:
		log.Fatalf("Unknown mode: %s. Use wfc, iack, or loadaware", *mode)
	}

	// Generate TLS configuration
	tlsConfig, err := generateTLSConfig()
	if err != nil {
		log.Fatalf("Failed to generate TLS cert: %v", err)
	}

	// Bind UDP socket and start QUIC listener
	listener, err := quic.ListenAddr(*addr, tlsConfig, quicConf)
	if err != nil {
		log.Fatalf("Failed to start QUIC listener: %v", err)
	}
	defer listener.Close()

	// Expose HTTP Metrics endpoint for Streamlit dashboard and telemetry scripts
	if *metricsAddr != "" {
		http.HandleFunc("/stats", func(w http.ResponseWriter, r *http.Request) {
			stats := statsHook()
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(stats)
		})
		go func() {
			if err := http.ListenAndServe(*metricsAddr, nil); err != nil && err != http.ErrServerClosed {
				log.Printf("[Server] Metrics server error: %v", err)
			}
		}()
		log.Printf("[Server] HTTP metrics available at http://%s/stats", *metricsAddr)
	}

	// Pre-generate standard 10KB application test payload
	payload := make([]byte, 10*1024)
	for i := range payload {
		payload[i] = byte(i % 256)
	}

	// Graceful shutdown handling on SIGINT/SIGTERM
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		log.Println("\n[Server] Shutting down...")
		log.Printf("[Server] Final Stats: %s", stringHook())
		listener.Close()
		os.Exit(0)
	}()

	log.Printf("[Server] Ready and accepting QUIC connections...")

	// Main connection accept loop
	for {
		conn, err := listener.Accept(context.Background())
		if err != nil {
			log.Printf("[Server] Listener closed or accept error: %v", err)
			break
		}

		// Handle each connection concurrently in a lightweight goroutine
		go func(c quic.Connection) {
			stream, err := c.AcceptStream(context.Background())
			if err != nil {
				return
			}
			defer stream.Close()

			// Read client request (e.g. "GET /10k")
			buf := make([]byte, 64)
			_, _ = stream.Read(buf)

			// Write 10KB test payload (enables measuring Time to First Byte - TTFB)
			_, _ = stream.Write(payload)
			_ = stream.Close()

			// Maintain connection until client completes or reaches idle timeout
			<-c.Context().Done()
		}(conn)
	}
}
