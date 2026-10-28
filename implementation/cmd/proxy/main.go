package main

import (
	"flag"
	"log"
	"math/rand"
	"net"
	"sync"
	"sync/atomic"
	"time"
)

/*
========================================================================================
 ASYNCHRONOUS USER-SPACE UDP NETWORK EMULATOR (PROXY)
========================================================================================

 1. PURPOSE & ARCHITECTURAL MOTIVATION:
    In Linux environments, network impairment testing is often achieved via `tc netem`.
    However, on macOS and inside containerized sandbox environments without root privileges,
    kernel-level packet manipulation is restricted.
    
    This user-space UDP proxy intercepts all datagrams between the client and server to
    simulate realistic WAN network topologies with precision:
      - Network RTT: Injects half of the RTT into both uplink (C2S) and downlink (S2C).
      - Packet Loss: Independent pseudorandom drop probability for uplink and downlink.
      - Delay Jitter: Random Gaussian-style latency variations simulating 5G/wireless links.

 2. SOCKET BUFFER ENGINEERING:
    To prevent false packet loss caused by OS-level buffer overflow during high-concurrency
    experiments (e.g. 50-client bursts), socket buffers are explicitly configured to 4MB:
    `uc.SetReadBuffer(4 * 1024 * 1024)`
========================================================================================
*/

type ProxyStats struct {
	ClientPacketsFwd  atomic.Int64
	ClientPacketsDrop atomic.Int64
	ServerPacketsFwd  atomic.Int64
	ServerPacketsDrop atomic.Int64
}

// getDelay calculates one-way transit delay factoring in network jitter
func getDelay(baseDelay, jitter time.Duration) time.Duration {
	if jitter <= 0 {
		return baseDelay
	}
	// Uniform jitter distribution centered around baseDelay: [-jitter/2, +jitter/2]
	delta := time.Duration((rand.Float64()*2.0 - 1.0) * float64(jitter/2))
	d := baseDelay + delta
	if d < time.Millisecond {
		d = time.Millisecond // Guarantee non-negative forward delay
	}
	return d
}

func main() {
	listenAddr := flag.String("listen", "127.0.0.1:6000", "UDP proxy listen address (client connects here)")
	targetAddr := flag.String("target", "127.0.0.1:4433", "UDP target address (QUIC server)")
	rtt := flag.Duration("rtt", 20*time.Millisecond, "Simulated round-trip time (split into 2 one-way delays)")
	lossRate := flag.Float64("loss", 0.0, "Packet loss rate (0.0 to 1.0)")
	lossC2S := flag.Float64("loss-c2s", -1.0, "Client-to-server loss rate (-1 to inherit from loss)")
	lossS2C := flag.Float64("loss-s2c", -1.0, "Server-to-client loss rate (-1 to inherit from loss)")
	jitter := flag.Duration("jitter", 0, "Simulated network delay jitter (e.g., 20ms)")
	flag.Parse()

	// Configure symmetric or asymmetric drop rates
	c2sRate := *lossRate
	if *lossC2S >= 0 {
		c2sRate = *lossC2S
	}
	s2cRate := *lossRate
	if *lossS2C >= 0 {
		s2cRate = *lossS2C
	}

	oneWayDelay := *rtt / 2

	log.Printf("[Proxy] Starting UDP network emulator on %s -> %s", *listenAddr, *targetAddr)
	log.Printf("[Proxy] Network conditions: RTT=%v (one-way=%v), C2S Loss=%.2f%%, S2C Loss=%.2f%%, Jitter=%v",
		*rtt, oneWayDelay, c2sRate*100, s2cRate*100, *jitter)

	serverUDPAddr, err := net.ResolveUDPAddr("udp", *targetAddr)
	if err != nil {
		log.Fatalf("Failed to resolve target: %v", err)
	}

	proxyConn, err := net.ListenPacket("udp", *listenAddr)
	if err != nil {
		log.Fatalf("Failed to listen on proxy addr: %v", err)
	}
	defer proxyConn.Close()

	// Enlarge OS kernel UDP socket buffers to 4MB to prevent drops during connection bursts
	if uc, ok := proxyConn.(*net.UDPConn); ok {
		_ = uc.SetReadBuffer(4 * 1024 * 1024)
		_ = uc.SetWriteBuffer(4 * 1024 * 1024)
	}

	stats := &ProxyStats{}

	// NAT-like table: maps each client endpoint (IP:Port) to its dedicated outbound server UDP socket
	var mu sync.Mutex
	clientToServer := make(map[string]*net.UDPConn)

	buf := make([]byte, 65535)

	// Ingress loop: reads client packets and forwards them to the server
	for {
		n, clientAddr, err := proxyConn.ReadFrom(buf)
		if err != nil {
			log.Printf("[Proxy] Error reading from client: %v", err)
			continue
		}

		// Uplink loss simulation (Client -> Server)
		if c2sRate > 0 && rand.Float64() < c2sRate {
			stats.ClientPacketsDrop.Add(1)
			continue // Drop packet
		}
		stats.ClientPacketsFwd.Add(1)

		packetData := make([]byte, n)
		copy(packetData, buf[:n])

		clientKey := clientAddr.String()

		mu.Lock()
		serverConn, exists := clientToServer[clientKey]
		if !exists {
			// Allocate new dedicated outgoing UDP socket to communicate with server for this client
			serverConn, err = net.DialUDP("udp", nil, serverUDPAddr)
			if err != nil {
				mu.Unlock()
				log.Printf("[Proxy] Failed to dial server: %v", err)
				continue
			}
			clientToServer[clientKey] = serverConn
			mu.Unlock()

			// Egress loop: reads server response datagrams and forwards them back to this client
			go func(cAddr net.Addr, sConn *net.UDPConn) {
				sBuf := make([]byte, 65535)
				for {
					sn, err := sConn.Read(sBuf)
					if err != nil {
						break
					}

					// Downlink loss simulation (Server -> Client)
					if s2cRate > 0 && rand.Float64() < s2cRate {
						stats.ServerPacketsDrop.Add(1)
						continue // Drop packet
					}
					stats.ServerPacketsFwd.Add(1)

					sData := make([]byte, sn)
					copy(sData, sBuf[:sn])

					// Delay server response by oneWayDelay + jitter in an asynchronous goroutine
					go func(data []byte) {
						d := getDelay(oneWayDelay, *jitter)
						if d > 0 {
							time.Sleep(d)
						}
						_, _ = proxyConn.WriteTo(data, cAddr)
					}(sData)
				}
			}(clientAddr, serverConn)
		} else {
			mu.Unlock()
		}

		// Delay client -> server packet by oneWayDelay + jitter in an asynchronous goroutine
		go func(conn *net.UDPConn, data []byte) {
			d := getDelay(oneWayDelay, *jitter)
			if d > 0 {
				time.Sleep(d)
			}
			_, _ = conn.Write(data)
		}(serverConn, packetData)
	}
}
