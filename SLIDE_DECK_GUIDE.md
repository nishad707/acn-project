# Comprehensive Slide Deck & Presentation Guide
## Load-Aware QUIC Instant ACK: Balancing Handshake Latency and Server Contention

> **Course**: COL724 / COL7524: Advanced Computer Networks (IIT Delhi, Semester 1, 2026–27)  
> **Milestone 2**: Progress Presentation (October 28, 2026)  
> **Team Members**:
> - **Muhammed Nishad** (2026MCS2799) — Presenting Part 1 (Slides 1–9) & Progress Summary (Slide 18)
> - **Ayush Arya** (2026MCS2802) — Presenting Part 2 (Slides 10–17) & Future Work / v2 (Slides 19–21)  
> **Base Research Paper**: *ReACKed QUICer: Measuring the Performance of Instant Acknowledgments in QUIC Handshakes* (ACM IMC 2024)  
> **Presentation Artifacts**:
> - 📊 PowerPoint Presentation: [`Load_Aware_QUIC_Instant_ACK_Presentation.pptx`](file:///b:/Mtech%20First%20Sem/Adv%20comp%20netw/Project/New%20folder/ACN_Presentation_Package/Load_Aware_QUIC_Instant_ACK_Presentation.pptx)
> - 🌐 Interactive Web Deck: [`presentation.html`](file:///b:/Mtech%20First%20Sem/Adv%20comp%20netw/Project/New%20folder/ACN_Presentation_Package/presentation.html)
> - 🔴 Real-Time Streamlit Dashboard: `streamlit run implementation/dashboard/app.py`

---

## 🧭 Executive Presentation Overview (21 Slides)

| # | Slide Title | Category | Presenter | Embedded Visual Asset |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **Title Slide & Team Context** | Overview | Both | Project Banner & IIT Delhi Badge |
| **2** | **Modern Edge CDNs & Certificate Delay (Δt)** | Context & Motivation | Muhammed | `diag_cdn_architecture.png` |
| **3** | **ReACKed QUICer: Base Paper & Key Idea** | Base Research Paper | Muhammed | `diag_handshake_flow.png` |
| **4** | **RFC 9002 Timer Math: PTO Inflation** | Theoretical Mechanics | Muhammed | Timer Equation & Numerical Box |
| **5** | **The Vulnerability of Static IACK: Probe Storms** | Problem & Blind Spot | Muhammed | Contention Failure Sequence |
| **6** | **Load-Aware QUIC Instant ACK: Core Thesis** | Proposed Extension | Muhammed | Dual-Regime Control Diagram |
| **7** | **The Control Engine: Schmitt-Trigger Hysteresis** | Proposed Extension | Muhammed | `diag_hysteresis_state_machine.png` |
| **8** | **Implementation Stack & quic-go Architecture** | Work Completed | Muhammed | `diag_system_architecture.png` |
| **9** | **Experimental Testbed & Parameter Matrix** | Methodology | Muhammed | Parameter Table & Specs Box |
| **10** | **Fig 1: Handshake Latency vs Network RTT** | Results & Findings | Ayush | `fig1_handshake_latency_vs_rtt.png` |
| **11** | **Fig 2: Time to First Byte (TTFB) Scaling** | Results & Findings | Ayush | `fig2_ttfb_vs_rtt.png` |
| **12** | **Fig 3: Handshake Scalability Under Concurrency** | Results & Findings | Ayush | `fig3_latency_under_load.png` |
| **13** | **Fig 4: Autonomous Decision Transitions** | Results & Findings | Ayush | `fig4_policy_decision_transition.png` |
| **14** | **Fig 5: Certificate Delay Sweep & PTO Crossover** | Results & Findings | Ayush | `fig5_cert_delay_sweep_crossover.png` |
| **15** | **Fig 6: Phased Handshake Decomposition (t1–t4)** | Results & Findings | Ayush | `fig6_phase_wait_time_breakdown.png` |
| **16** | **Fig 7: Hysteresis Threshold Sensitivity Sweep** | Results & Findings | Ayush | `fig7_threshold_sensitivity.png` |
| **17** | **Fig 8: 2D Operational Space Winner Map** | Results & Findings | Ayush | `fig8_winner_heatmap.png` |
| **18** | **Milestone 2 Deliverables & Tooling Summary** | Progress Summary | Muhammed | Milestone Checklist & Dashboard Card |
| **19** | **Future Work 1: Stress Test Discoveries & Trade-Offs** | Future Work | Ayush | `diag_stress_tests_summary.png` |
| **20** | **Future Work 2: Load-Aware v2 & Milestone 3 Roadmap** | Future Work | Ayush | `diag_v1_vs_v2_comparison.png` |
| **21** | **Conclusion, Live Demo & Q&A Defense** | Conclusion & Defense | Both | Defense Q&A Sheet & Demo Links |

---

## 🎙️ Detailed Slide-by-Slide Guide & Verbal Scripts

---

### Slide 1: Title Slide & Project Overview
* **Category**: Project Overview
* **Slide Title**: Load-Aware QUIC Instant ACK: Balancing Handshake Latency and Server Contention in Modern Edge CDNs
* **Presenter**: Muhammed Nishad & Ayush Arya
* **Slide Content**: Minimalist layout with Course Name (COL724/COL7524), Project Title, Presenter Names & Entry Numbers, Department of Computer Science & Engineering, IIT Delhi, and Base Paper citation (ACM IMC 2024).
* **Verbal Script (Muhammed Nishad)**:
  > *"Good morning professors and colleagues. Today Ayush Arya and I are presenting our Advanced Computer Networks progress presentation on **Load-Aware QUIC Instant ACK**. Our work builds upon the recent ACM IMC 2024 research paper 'ReACKed QUICer'. In this project, we explore connection setup performance in modern edge networks, expose a fundamental vulnerability in static Instant ACK under server concurrency, and present an autonomous, closed-loop solution that balances client latency with server stability."*

---

### Slide 2: Context — Modern Edge CDN Architectures & QUIC
* **Category**: Context & Motivation
* **Slide Title**: Modern Edge CDNs & The Certificate Delay Gap ($\Delta t$)
* **Subtitle Takeaway**: *Edge proxies terminate QUIC handshakes, but TLS certificate signing introduces internal delay.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: `figures/diag_cdn_architecture.png` (Three-tier diagram: Client $\leftrightarrow$ CDN Edge PoP $\leftrightarrow$ Centralized Keyless SSL / Backend Cert Store).
* **On-Slide Bullets**:
  * **The Edge/Backend Split**: Modern CDNs (Cloudflare, Akamai) terminate QUIC at distributed edge PoPs, while certificates and private keys remain in centralized backend stores (Keyless SSL).
  * **Backend Delay ($\Delta t$)**: Fetching certificates, computing RSA/ECDSA cryptographic signatures, or queueing introduces an internal delay $\Delta t$ (typically 2 ms to 200 ms).
  * **The Protocol Dilemma**: While waiting for the certificate, should the server wait and send 1 coalesced flight, or immediately acknowledge the client?
* **Verbal Script (Muhammed Nishad)**:
  > *"To understand the motivation behind our project, look at Figure 2 on the left. In modern Content Delivery Networks like Cloudflare and Akamai, QUIC handshakes terminate at distributed Edge PoPs close to the user. However, due to regulatory compliance, security policies, and centralized key management—often termed Keyless SSL—the server's private keys and TLS certificates are hosted in centralized backend stores.  
  > This architectural separation means the edge server experiences an internal delay $\Delta t$, typically between 2 to 200 milliseconds, to retrieve or sign cryptographic credentials. The fundamental transport question is: while the edge server waits for this certificate, how should it respond to the incoming `ClientHello`?"*

---

### Slide 3: Base Paper & Key Idea — ReACKed QUICer (ACM IMC 2024)
* **Category**: Base Research Paper
* **Slide Title**: ReACKed QUICer: Measuring Instant ACKs (ACM IMC 2024)
* **Subtitle Takeaway**: *Jonas Mücke, Marcin Nawrocki, Raphael Hiesgen, Thomas C. Schmidt, Matthias Wählisch*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: `figures/diag_handshake_flow.png` (Sequence diagrams comparing WFC, IACK, and Contention Failure).
* **On-Slide Bullets**:
  * **Status Quo (WFC)**: Wait-for-Certificate — Server waits for $\Delta t$, then coalesces `Initial[ACK, Crypto]` + `Handshake[Crypto]` into 1 UDP packet flight.
  * **The Paper's Proposal (IACK)**: Instant ACK — Server immediately transmits an uncoalesced `Initial[ACK]`, sending the certificate flight later.
  * **Reported Benefit**: Delivers 15–20 ms faster connection setups across realistic network paths.
  * **The Scope**: Evaluated exclusively under static network settings on idle servers.
* **Verbal Script (Muhammed Nishad)**:
  > *"The research paper we selected is 'ReACKed QUICer', published at ACM IMC 2024. In standard QUIC, implementations employ Wait-for-Certificate (WFC): the server delays its response until the certificate arrives, then coalesces the Initial ACK and Handshake crypto frames into a single UDP datagram.  
  > The IMC '24 authors proposed Instant ACK (IACK): the server immediately transmits an `Initial[ACK]` back to the client upon receiving `ClientHello`, and sends the certificate in a second flight once it is ready. They demonstrated that this yields a 15 to 20 millisecond reduction in handshake completion time across Internet paths. However, their study evaluated IACK solely under static network conditions on idle servers."*

---

### Slide 4: Theoretical Mechanics — Probe Timeout (PTO) Inflation
* **Category**: Theoretical Mechanics
* **Slide Title**: RFC 9002 Timer Math: Probe Timeout (PTO) Inflation
* **Subtitle Takeaway**: *Under Wait-for-Certificate, internal server delay artificially inflates the client's loss recovery timer.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: Mathematical formulation card + Numerical Walkthrough comparison card ($RTT=20\text{ms}, \Delta t=50\text{ms}$).
* **On-Slide Bullets**:
  * **RFC 9002 Initial PTO**: $\text{PTO}_{\text{initial}} \approx \text{smoothed\_rtt} + 4 \times \text{rttvar} \approx 3 \times \text{RTT}_{\text{measured}}$.
  * **WFC Timer Inflation**: Client measures $\text{RTT} + \Delta t \implies \text{PTO}_{\text{WFC}} = 3 \times (\text{RTT} + \Delta t)$.
  * **Instant ACK Calibration**: Client measures true network $\text{RTT} \implies \text{PTO}_{\text{IACK}} = 3 \times \text{RTT}$.
  * **The $3\times\Delta t$ Loss Penalty**: If packet loss occurs, WFC stalls recovery by $3\times\Delta t$ (e.g., +150 ms stall for a 50 ms cert delay).
* **Verbal Script (Muhammed Nishad)**:
  > *"Why does Instant ACK help? The answer lies in the loss recovery mathematics of RFC 9002. The initial Probe Timeout is computed as smoothed RTT plus 4 times RTTVAR, which reduces to roughly 3 times the measured initial RTT.  
  > In Wait-for-Certificate, the client's clock measures network RTT plus backend delay $\Delta t$. If true RTT is 20ms and cert delay is 50ms, the client measures 70ms and sets its PTO to 210ms!  
  > In Instant ACK, because the client receives an ACK after exactly 1 RTT, it calibrates its timer to 60ms. If packet loss drops the certificate flight, Instant ACK detects the drop and fires a recovery probe in 60ms, whereas WFC stalls for 210ms—a massive 150ms penalty."*

---

### Slide 5: The Critical Blind Spot of Static IACK
* **Category**: Problem Statement & Blind Spot
* **Slide Title**: The Vulnerability of Static IACK: Probe Storms Under Load
* **Subtitle Takeaway**: *When server contention delays certificates beyond the tight PTO, clients trigger spurious probe storms.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: Contention Failure sequence diagram (Focus on Panel 3 of `diag_handshake_flow.png`).
* **On-Slide Bullets**:
  * **Syscall & Buffer Pressure**: Static IACK emits 2 separate UDP datagrams per connection instead of 1. Under surges, this doubles `sendmsg` syscalls and socket buffer consumption.
  * **The Crossover Failure Condition**: If server CPU starvation or crypto worker queues delay the certificate flight such that $\Delta t_{\text{effective}} > 3 \times \text{RTT}_{\text{net}}$.
  * **Premature Timer Expiration**: The client's tight PTO timer expires before the certificate packet arrives!
  * **Spurious PTO Probe Storms**: Clients flood the server with PTO probe packets right when the server is already bottlenecked, causing UDP packet drops and handshake collapse.
* **Verbal Script (Muhammed Nishad)**:
  > *"Now, here is the critical vulnerability that the original paper missed. In high-density production environments, edge servers experience concurrent handshakes, socket buffer pressure, and CPU contention.  
  > Static IACK introduces two fatal flaws. First, emitting two datagrams per connection doubles `sendmsg` system calls and socket buffer utilization right during a traffic burst.  
  > Second, if server queueing stretches effective certificate delay beyond 3 times RTT, the client's tight PTO timer expires before the certificate arrives! The client falsely assumes the flight was lost and floods the server with spurious PTO probes. Under a burst of 500 or 1,000 clients, this triggers a thundering herd probe storm that crashes server goodput."*

---

### Slide 6: Proposed Improvement — Load-Aware QUIC Instant ACK
* **Category**: Proposed Extension
* **Slide Title**: Load-Aware QUIC Instant ACK: Adaptive Closed-Loop Control
* **Subtitle Takeaway**: *Dynamically evaluate server contention to balance low handshake latency and overload protection.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: Two-column architectural comparison card (Peacetime low-latency mode vs. Surge coalescing mode).
* **On-Slide Bullets**:
  * **The Core Thesis**: Server-side contention (active handshakes, CPU load) should actively govern the ACK policy in real time.
  * **Peacetime / Low Contention**: Deploy **Instant ACK** $\implies$ True RTT calibration, tight initial PTO ($3\times\text{RTT}$), and 15–20 ms speedup.
  * **Surge / High Contention**: Fallback to **WFC / Coalescing** $\implies$ Halves `sendmsg` syscall volume, protects socket buffers, suppresses probe storms.
  * **100% Client Compatible**: Fully compliant with RFC 9000 & 9002; requires zero changes to client browsers or mobile stacks.
* **Verbal Script (Muhammed Nishad)**:
  > *"Our proposed improvement is **Load-Aware QUIC Instant ACK**. We ask: can server contention serve as an active closed-loop feedback signal?  
  > Instead of locking the server into a rigid static policy, our server dynamically evaluates its contention level. During peacetime, when headroom is available, it deploys Instant ACK to grant clients fast RTT calibration and rapid loss recovery.  
  > But when a traffic spike arrives, the server autonomously falls back to single-flight coalesced WFC. This immediately cuts system calls by 50%, protects the UDP socket buffer, and completely eliminates spurious probe storms. Crucially, this requires zero modifications to client software and fully adheres to RFC 9000."*

---

### Slide 7: Control Engine — Schmitt-Trigger Hysteresis Controller
* **Category**: Proposed Extension
* **Slide Title**: The Control Engine: Schmitt-Trigger Hysteresis Controller
* **Subtitle Takeaway**: *Dual-threshold deadband eliminates mode-flapping and ensures rock-solid operational stability.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: `figures/diag_hysteresis_state_machine.png` (State machine showing State IACK, State WFC, and the $[4, 8]$ deadband).
* **On-Slide Bullets**:
  * **Switch to WFC**: Active Handshakes $\ge \tau_{\text{high}}$ (8) $\implies$ Contention protection: shift to coalesced WFC.
  * **Switch to IACK**: Active Handshakes $\le \tau_{\text{low}}$ (4) $\implies$ Headroom available: shift to Instant ACK.
  * **Deadband $[4, 8]$**: When active handshakes are between 4 and 8, maintain previous state.
  * **Why Hysteresis?**: A single threshold (e.g., at 6) would cause rapid mode-flapping under oscillating traffic, thrashing server state and degrading client timers.
* **Verbal Script (Muhammed Nishad)**:
  > *"To ensure stable switching, we designed a Schmitt-trigger closed-loop hysteresis controller, implemented in `loadmonitor.go`.  
  > If we used a single threshold—say, 6 active connections—any traffic oscillating around 6 would cause rapid mode-flapping, creating severe timer instability for clients.  
  > Instead, we established a dual-threshold deadband: $\tau_{\text{low}}=4$ and $\tau_{\text{high}}=8$. When active handshakes surge to 8, the server shifts to coalescing. It only switches back to Instant ACK once load drops to 4 or below. Within the deadband, it preserves its prior state, ensuring zero mode-flapping."*

---

### Slide 8: System Implementation & Architecture
* **Category**: Work Completed So Far
* **Slide Title**: Implementation Stack & Experimental Testbed Architecture
* **Subtitle Takeaway**: *Complete end-to-end QUIC measurement testbed built on Go 1.20.7 and modified quic-go.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: `figures/diag_system_architecture.png` (Block diagram linking Measurement Client, UDP Proxy Emulator, QUIC Server, and Streamlit Dashboard).
* **On-Slide Bullets**:
  * **quic-go & qtls-go1-20**: Pinned to dedicated Go 1.20.7 runtime to access internal TLS 1.3 handshake secrets.
  * **Engine Hook**: Integrated into `connection.go:handleUnpackedLongHeaderPacket()` to dynamically query `LoadMonitor`.
  * **UDP Proxy Emulator**: Asynchronous proxy (`cmd/proxy`) with 4MB socket buffers, delay injection, jitter, and loss.
  * **Measurement Client**: Multi-worker goroutines measuring TTFB, phases $t_1-t_4$, and RFC 9002 PTO probe counts.
* **Verbal Script (Muhammed Nishad)**:
  > *"Slide 8 depicts our complete implementation architecture. We built upon the IMC '24 authors' fork of `quic-go`, which relies on `qtls-go1-20` to access TLS 1.3 internal secrets.  
  > We implemented three core Go components: a multi-mode QUIC server (`cmd/server`) that hooks into `connection.go` to query `LoadMonitor`; an asynchronous user-space UDP proxy (`cmd/proxy`) that injects bidirectional RTT delay, packet loss, and jitter with 4MB socket buffers; and a multi-threaded measurement client (`cmd/client`) that captures high-precision timestamps and RFC 9002 PTO probes. We also built an interactive Streamlit dashboard at port 8501."*

---

### Slide 9: Evaluation Methodology & Experimental Matrix
* **Category**: Evaluation Methodology
* **Slide Title**: Experimental Testbed Specifications & Evaluation Matrix
* **Subtitle Takeaway**: *Standardized benchmark testbed designed for rigorous scientific reproducibility.*
* **Presenter**: Muhammed Nishad (Handing over to Ayush Arya)
* **Visual Asset**: Two-column matrix card (Testbed hardware/software specifications vs. Experimental parameter grid).
* **On-Slide Bullets**:
  * **Host Hardware**: Apple Silicon M-series (8 execution cores, 16GB unified memory).
  * **Kernel Buffers**: UDP socket buffers expanded to **4MB** (`SetReadBuffer`) to eliminate loopback packet drops.
  * **Evaluated Policies (3)**: Static WFC vs. Static IACK vs. Load-Aware IACK (Ours).
  * **Parameter Matrix**: 4 Network RTTs (10 to 100ms), 5 Cert Delays (5 to 180ms), Concurrency up to 75 (baseline) and 5,000 (stress), Packet Loss (0–8%), Jitter ($\pm 45$ms).
* **Verbal Script (Muhammed Nishad)**:
  > *"To ensure scientific rigor, all benchmarks were executed under standardized testbed parameters. Our host environment is an 8-core Apple Silicon system running Go 1.20.7, with OS UDP socket buffers configured to 4MB to eliminate kernel-level loopback packet drops.  
  > Our experimental matrix tests all three policies across 4 path RTTs, 5 backend certificate delays, concurrency levels scaling from 1 to 75 in baseline and up to 5,000 in stress tests, and loss rates up to 8%.  
  > I will now hand over to Ayush Arya to walk you through our empirical results and findings."*

---

### Slide 10: Finding 1 — Handshake Latency vs. Path RTT (Peacetime)
* **Category**: Results & Findings
* **Slide Title**: Figure 1: Handshake Latency vs. Network RTT (Peacetime)
* **Subtitle Takeaway**: *Under peacetime, Load-Aware reliably chooses Instant ACK, matching the 15–20 ms speedup across all RTTs.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig1_handshake_latency_vs_rtt.png` (Handshake completion time vs. RTT from 10ms to 100ms, $\Delta t = 20\text{ms}$).
* **On-Slide Bullets**:
  * **Peacetime Optimality**: Under light load (1–3 clients), Load-Aware detects zero contention and deploys 100% Instant ACK.
  * **Consistent 15–20ms Speedup**: At RTT=10ms: WFC is 36.6 ms, Load-Aware is **34.2 ms**. At RTT=60ms: WFC is 101.2 ms, Load-Aware is **85.0 ms (16.2 ms faster!)**.
  * **Zero Overhead**: Load-Aware curve (green) overlaps Static IACK (orange) within $<0.5\text{ms}$ variance.
* **Verbal Script (Ayush Arya)**:
  > *"Thank you Muhammed. Turning to our results, Figure 1 plots handshake completion time against network RTT from 10 to 100 milliseconds under peacetime conditions with a 20ms certificate delay.  
  > As you can see, our Load-Aware policy in green perfectly tracks Static IACK in orange across the entire curve. At 10ms RTT, Load-Aware finishes in 34.2ms compared to 36.6ms for WFC. At 60ms RTT, WFC requires 101.2ms, while Load-Aware finishes in 85.0ms—a 16.2ms latency improvement. This confirms that during peacetime, Load-Aware introduces zero measurable overhead and captures the full latency advantages of Instant ACK."*

---

### Slide 11: Finding 2 — Time to First Byte (TTFB) Verification
* **Category**: Results & Findings
* **Slide Title**: Figure 2: Time to First Byte (TTFB) vs. Network RTT
* **Subtitle Takeaway**: *TTFB scales linearly with path RTT, confirming Instant ACK introduces zero application-layer delay.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig2_ttfb_vs_rtt.png` (TTFB vs. Network RTT across WFC, IACK, and Load-Aware).
* **On-Slide Bullets**:
  * **Why TTFB Matters**: Verifies when the client application actually receives the first HTTP/3 stream payload data byte.
  * **Linear Scaling**: TTFB scales strictly linearly with RTT across all 3 modes (~35ms at 10ms $\to$ ~126ms at 100ms).
  * **Zero Payload Penalty**: Splitting the handshake flight in IACK does not delay 1-RTT stream application delivery.
* **Verbal Script (Ayush Arya)**:
  > *"In Figure 2, we evaluated Time to First Byte (TTFB) to examine application-layer performance. A natural concern is whether splitting the server's initial response into two separate datagrams introduces any delay in delivering actual application stream data.  
  > Figure 2 clearly shows that TTFB scales linearly with network path RTT and is indistinguishable across all three policies. This confirms that optimizing initial packet timing does not introduce any penalty for subsequent HTTP/3 payload transfer."*

---

### Slide 12: Finding 3 — Handshake Latency Under Concurrency (The Core Thesis)
* **Category**: Results & Findings
* **Slide Title**: Figure 3: Handshake Scalability Under Concurrency (Core Thesis)
* **Subtitle Takeaway**: *Static IACK degrades sharply to 128+ ms under concurrency; Load-Aware caps latency at 102 ms (~20% speedup).*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig3_latency_under_load.png` (Median and p95 Handshake Latency across 1 to 75 concurrent clients).
* **On-Slide Bullets**:
  * **Static IACK Breakdown**: As concurrency grows from 1 to 50 clients, Static IACK jumps from 46.1 ms to **128.8 ms** (and 148 ms at 75 clients) due to syscall doubling and socket buffer congestion.
  * **Load-Aware Throttling**: Crosses $\tau_{\text{high}}=8$ and transitions to WFC, capping median latency at **102.8 ms (20.2% faster)**.
  * **Tail Latency Bounded**: p95 tail latency (dashed lines) remains tightly bounded under Load-Aware, avoiding the severe tail blowout of Static IACK.
* **Verbal Script (Ayush Arya)**:
  > *"Figure 3 presents the core thesis of our research. Here, we ramped concurrent client handshakes from 1 up to 75.  
  > Look at the orange curve for Static IACK: as concurrency reaches 50 clients, median latency jumps from 46ms to 128.8ms, and reaches 148ms at 75 clients. Static IACK degrades because emitting two packets per connection doubles system call overhead and congests the socket queue.  
  > Now look at our green Load-Aware curve: as soon as concurrency crosses our threshold of 8, the engine transitions to coalesced WFC, capping median latency at 102.8ms—a 20.2% improvement over Static IACK, while keeping p95 tail latency strictly bounded."*

---

### Slide 13: Finding 4 — Autonomous Policy Decision Transition
* **Category**: Results & Findings
* **Slide Title**: Figure 4: Autonomous Closed-Loop Decision Transition
* **Subtitle Takeaway**: *Stacked bar chart showing the automated shift from 100% IACK to 93%+ WFC fallback as load surges.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig4_policy_decision_transition.png` (Stacked bar chart: green IACK decisions vs. blue WFC fallback decisions across client loads).
* **On-Slide Bullets**:
  * **1 to 5 Clients**: 100% IACK decisions (green). Server operates in Fast-PTO low-latency mode.
  * **10 Clients (Threshold)**: 70% IACK / 30% WFC. Active handshakes cross $\tau_{\text{high}}=8$; throttling initiates.
  * **50 Clients (Surge Overload)**: **93%+ WFC decisions**. Connections coalesce into WFC, shielding socket buffers.
* **Verbal Script (Ayush Arya)**:
  > *"Figure 4 reveals the internal dynamics of our decision engine during that concurrency ramp. The green bars represent Instant ACK decisions, while the blue bars represent WFC coalescing decisions.  
  > At 1 to 5 clients, the server makes 100% IACK decisions. At 10 clients, as load crosses our threshold of 8, it begins shifting connections to WFC. By 50 clients, over 93% of connections are autonomously coalesced into single-flight WFC. This proves that the closed-loop controller successfully protects the kernel socket buffers without requiring manual administrator intervention."*

---

### Slide 14: Finding 5 — Certificate Delay Sweep & PTO Crossover
* **Category**: Results & Findings
* **Slide Title**: Figure 5: Certificate Delay Sweep & The PTO Crossover Boundary
* **Subtitle Takeaway**: *Empirical validation of the theoretical failure boundary ($\Delta t > 3 \times \text{RTT}$) where Static IACK collapses.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig5_cert_delay_sweep_crossover.png` (Handshake latency vs. Cert Delay $\Delta t$ from 10ms to 180ms, RTT = 40ms, initial PTO = 120ms).
* **On-Slide Bullets**:
  * **Setup**: RTT = 40 ms $\implies$ Initial Client PTO = $3 \times 40\text{ ms} = \mathbf{120\text{ ms}}$ (marked by red dotted line).
  * **Below Boundary ($\Delta t < 120\text{ms}$)**: IACK completes cleanly before client PTO timer expires.
  * **Beyond Boundary ($\Delta t > 120\text{ms}$)**: Static IACK triggers premature client timeouts and spurious retransmissions.
  * **Load-Aware Immunity**: Load-Aware seamlessly avoids probe storms and scales smoothly.
* **Verbal Script (Ayush Arya)**:
  > *"Figure 5 provides direct empirical validation of the theoretical failure condition we derived earlier. In this experiment, path RTT was 40ms, which means the client's initial PTO was exactly 3 times 40, or 120ms, marked by the red dotted line.  
  > We swept backend certificate delay from 10ms to 180ms. As long as cert delay remained below 120ms, Static IACK performed well. But once cert delay crossed 120ms, the client's tight PTO expired before the certificate arrived, triggering premature timeouts and retransmissions. Load-Aware detects this inflation and avoids timer breakdown entirely."*

---

### Slide 15: Finding 6 — Phased Handshake Decomposition ($t_1 \text{--} t_4$)
* **Category**: Results & Findings
* **Slide Title**: Figure 6: Phased Handshake Decomposition ($t_1$ to $t_4$)
* **Subtitle Takeaway**: *Deconstructs handshake wait times: under load, Static IACK certificate gap ($t_2$) balloons due to queueing.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig6_phase_wait_time_breakdown.png` (Two-panel stacked bar chart: Low Contention on left vs. High Contention on right).
* **On-Slide Bullets**:
  * **Phases**: $t_1$ = 1st server packet, $t_2$ = cert wait gap, $t_3$ = finish, $t_4$ = TTFB response.
  * **Low Contention**: IACK cuts $t_1$ from 30ms to 10ms; $t_2$ equals pure cert delay (20ms).
  * **High Contention**: In Static IACK, $t_2$ balloons to 65+ ms due to socket buffer queueing and context switching.
  * **Load-Aware Resolution**: Eliminates the $t_2$ queueing penalty via single-flight coalescing.
* **Verbal Script (Ayush Arya)**:
  > *"In Figure 6, we instrumented our measurement client to decompose connection setup into four distinct timestamp intervals: $t_1$ is the time to receive the first server packet, $t_2$ is the wait gap for the certificate, $t_3$ is handshake completion, and $t_4$ is application TTFB.  
  > Under low contention on the left, IACK cuts $t_1$ to 10ms, while $t_2$ matches the 20ms cert delay. But look at the right graph under high contention: in Static IACK, $t_2$ balloons to over 65ms because uncoalesced ACK packets clog the socket queue. Load-Aware eliminates this queueing expansion by falling back to coalescing."*

---

### Slide 16: Finding 7 — Hysteresis Threshold Tuning
* **Category**: Results & Findings
* **Slide Title**: Figure 7: Hysteresis Threshold Sensitivity Sweep
* **Subtitle Takeaway**: *Proves that the deadband $[\tau_{\text{low}}=4, \tau_{\text{high}}=8]$ provides the optimal balance of agility and anti-flapping stability.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig7_threshold_sensitivity.png` (Median and p95 Latency across deadbands $[(2,4), (4,8), (8,16), (15,30)]$ at 25 concurrent clients).
* **On-Slide Bullets**:
  * **$[2, 4]$ Pair (Overly Sensitive)**: Mode-flaps on transient bursts, losing IACK benefits during brief spikes.
  * **$[15, 30]$ Pair (Too Sluggish)**: Reacts too late; socket buffers overflow before switching, blowing out p95 tail (>105ms).
  * **$[4, 8]$ Pair (The Optimal Deadband)**: Delivers lowest combined median (50.8 ms) and p95 tail (64.2 ms).
* **Verbal Script (Ayush Arya)**:
  > *"A critical design question for our hysteresis controller was how to select the threshold values. In Figure 7, we evaluated four deadband configurations at 25 concurrent connections: $[2,4], [4,8], [8,16],$ and $[15,30]$.  
  > We found that $[2,4]$ was overly sensitive, triggering unnecessary mode transitions on brief micro-bursts. Conversely, $[15,30]$ was too sluggish, waiting until socket buffers had already congested. The deadband $[\tau_{\text{low}}=4, \tau_{\text{high}}=8]$ offered the optimal balance, achieving the lowest median and tail latencies."*

---

### Slide 17: Finding 8 — 2D Parameter Winner Heatmap (Headline Figure)
* **Category**: Results & Findings
* **Slide Title**: Figure 8: 2D Operational Space Winner Map (Headline Figure)
* **Subtitle Takeaway**: *Visualizing the entire design space: static policies fail across half the regimes; Load-Aware dominates throughout.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/fig8_winner_heatmap.png` (2D Parameter Space Heatmap: Backend Cert Delay $\Delta t$ on x-axis $\times$ Concurrency Load on y-axis).
* **On-Slide Bullets**:
  * **Static Policies Fail**: Orange = Static IACK wins only in bottom-left. Blue = Static WFC wins only in top-right.
  * **The Static Flaw**: Any static configuration is suboptimal across 50% of real-world operating conditions!
  * **Load-Aware Dominance**: Green = Load-Aware dynamically chooses the winning policy across **100% of the entire 2D matrix**.
* **Verbal Script (Ayush Arya)**:
  > *"Figure 8 is our headline figure, mapping the complete two-dimensional operational space across Backend Certificate Delay on the x-axis and Concurrent Handshake Load on the y-axis.  
  > The orange region shows where Static IACK is optimal—strictly in the bottom-left under low load. The blue region shows where Static WFC is optimal—under heavy load. This proves that any static policy is guaranteed to fail in half the operating space. In contrast, the green shading shows that Load-Aware dynamically matches or beats the best static policy across 100% of the parameter space."*

---

### Slide 18: Summary of Work Completed So Far (Milestone 2 Status)
* **Category**: Progress Summary
* **Slide Title**: Work Completed So Far: Milestone 2 Deliverables
* **Subtitle Takeaway**: *Complete verification, engine implementation, empirical evaluation, and interactive tooling.*
* **Presenter**: Muhammed Nishad
* **Visual Asset**: Milestone 2 Checklist Completed card + Live Streamlit Dashboard preview card.
* **On-Slide Bullets**:
  * **Fork Verification**: Validated IMC '24 artifact repo on Go 1.20.7 + `qtls`.
  * **Multi-Mode Server**: Unified binary supporting WFC, IACK, and Load-Aware.
  * **Hysteresis Controller**: Built `loadmonitor.go` with $[4, 8]$ anti-flapping deadband.
  * **UDP Network Proxy**: Asynchronous proxy with nanosecond RTT, loss, and jitter.
  * **Empirical Results**: 8 baseline experiments completed with raw CSVs & publication plots.
  * **Live Streamlit Dashboard**: Real-time telemetry at `localhost:8501`.
* **Verbal Script (Muhammed Nishad)**:
  > *"To summarize our progress for Milestone 2: we have successfully cloned and verified the research artifact, established a dedicated Go 1.20 environment, designed and integrated our Schmitt-trigger LoadMonitor into `quic-go`, built a standalone UDP network proxy emulator and multi-worker measurement client, executed all 8 baseline experiments, and developed an interactive Streamlit monitoring dashboard. All code and benchmarks are fully automated and reproducible."*

---

### Slide 19: Future Work 1 — Stress Testing Discoveries & Theoretical Limits
* **Category**: Future Work & Next Directions
* **Slide Title**: Future Work 1: Stress Testing Insights & Theoretical Discoveries
* **Subtitle Takeaway**: *Beyond baseline: probing extreme adversarial regimes, flash crowds, and fundamental transport trade-offs.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/diag_stress_tests_summary.png` (Bar chart comparing WFC, IACK, and Load-Aware across 200 Flash Crowds, 500 Bursts, 5% Packet Loss, and Spurious PTO Probes).
* **On-Slide Bullets**:
  * **The "Hydraulic Relief" Effect (Exp B)**: In 200-client flash crowds, Load-Aware beats **both** static baselines simultaneously (337.7 ms vs 759.4 ms IACK and 920.9 ms WFC). Initial arrivals get fast IACK; subsequent arrivals coalesce into WFC.
  * **Loss Recovery Speedup (Exp C)**: Under 5% loss, WFC stalls to 328.6 ms due to inflated PTO. Load-Aware recovers in **129.9 ms (60.5% faster)**.
  * **CPU vs Socket Buffers (Exp A.1)**: 8 pegged cores showed <1ms variance. Socket queue drops drive collapse, not background compute.
  * **Hysteresis Stability (Exp D)**: Zero mode-flapping across 7 alternating surge/peacetime waves.
* **Verbal Script (Ayush Arya)**:
  > *"Looking toward our future work and Milestone 3, we pushed our v1 engine into extreme adversarial stress scenarios.  
  > In Experiment B, we tested an instantaneous flash crowd of 200 clients. Here, Load-Aware did not merely fall between WFC and IACK—it beat both static baselines simultaneously, completing in 337ms versus 759ms for IACK and 920ms for WFC!  
  > We call this the 'Hydraulic Relief Valve' effect: early arrivals capture Instant ACK speed, and as load passes 8, subsequent connections are throttled into coalesced WFC, protecting socket queues. We also discovered that pegging 8 CPU cores at 100% caused less than 1ms difference—proving that QUIC handshake collapse is driven by UDP socket buffer queueing and syscall volume, not background compute."*

---

### Slide 20: Future Work 2 — Load-Aware v2 Architecture & Milestone 3 Roadmap
* **Category**: Future Work & Next Directions
* **Slide Title**: Future Work 2: Load-Aware v2 Innovations & Research Roadmap
* **Subtitle Takeaway**: *Lock-free fast paths, arrival velocity prediction (dLoad/dt), token-bucket pacing, and Milestone 3 plans.*
* **Presenter**: Ayush Arya
* **Visual Asset**: `figures/diag_v1_vs_v2_comparison.png` (Head-to-head comparison chart: Load-Aware v1 vs. v2 across Flash Crowds, Surges, Jitter, and Probe Storms).
* **On-Slide Bullets**:
  * **Lock-Free Fast Path**: Replaced mutexes with atomic CAS registers. Decision latency dropped from ~150ns to **<5ns (30x faster)**.
  * **Arrival Velocity ($d\text{Load}/dt$)**: Predicts arrival rate via EWMA; pre-emptively shifts to WFC before socket queues fill.
  * **Token-Bucket Pacer**: Rate-limits uncoalesced ACK bursts during micro-surges.
  * **Benchmark Gains**: **32% faster** in 100-client flash crowds; **36.2% probe storm reduction** at 5,000 clients.
  * **Milestone 3 Roadmap**: Multi-client wide-area Internet testbeds, kernel eBPF socket queue depth, refinement towards v3.
* **Verbal Script (Ayush Arya)**:
  > *"To address the bottlenecks identified in stress testing, we have already prototyped Load-Aware v2.  
  > v2 introduces three architectural enhancements: first, a sub-5-nanosecond lock-free atomic fast-path that eliminates mutex convoying; second, arrival velocity prediction—computing $d\text{Load}/dt$ via EWMA to switch to WFC pre-emptively before socket buffers overflow; and third, an atomic token-bucket burst pacer.  
  > In preliminary benchmarks, v2 is 32% faster in flash crowds and reduces probe storms by 36.2% under 5,000 clients. For Milestone 3, we plan to validate these prototypes across wide-area Internet paths, explore kernel eBPF queue monitoring, and present our final refined v3 architecture."*

---

### Slide 21: Conclusion & Presentation Defense Readiness
* **Category**: Conclusion & Defense
* **Slide Title**: Conclusion, Live Demonstration & Q&A Defense
* **Subtitle Takeaway**: *Balancing handshake latency and server overhead through dynamic closed-loop load awareness.*
* **Presenter**: Muhammed Nishad & Ayush Arya
* **Visual Asset**: Summary Takeaways card + Presentation Defense Q&A Sheet.
* **On-Slide Bullets**:
  * **Fundamental Trade-Off Resolved**: Closed-loop load awareness captures Instant ACK latency speedup while completely avoiding probe storm collapse.
  * **Superiority Proven**: 20% latency reduction under concurrency, dominates 100% of the 2D parameter space, and beats both baselines in flash crowds.
  * **Standard Compliant**: 100% RFC 9000/9002 compatible with zero client-side changes.
  * **Live Dashboard**: Running live at `localhost:8501`.
* **Verbal Script (Muhammed Nishad & Ayush Arya)**:
  > *"In conclusion, Load-Aware QUIC Instant ACK successfully resolves the fundamental trade-off between handshake latency and server overhead in modern edge CDNs. We have validated our core thesis through 8 baseline experiments, verified the RFC 9002 crossover boundary, explored extreme stress limits, and prototyped lock-free v2 optimizations for Milestone 3.  
  > We also have our live Streamlit dashboard running and ready for demonstration. Thank you very much, and we are happy to take any questions."*

---

## 🛡️ Top 10 Tough Defense Questions & High-Scoring Answers

#### Q1: "Why did you pick threshold values 4 and 8? Why not 10 and 20?"
> **Answer**: *"We performed an empirical sensitivity sweep in Experiment 7 across $[(2,4), (4,8), (8,16), (15,30)]$. We found that $[2,4]$ was overly sensitive and mode-flapped on transient micro-bursts, while $[15,30]$ reacted too late after socket buffers had already begun queueing. The deadband $[\tau_{\text{low}}=4, \tau_{\text{high}}=8]$ offered the optimal balance between rapid response and anti-flapping stability."*

#### Q2: "Why is Load-Aware faster than BOTH WFC and IACK at 200 concurrent clients?"
> **Answer**: *"Because it acts as a dynamic hydraulic relief valve. Static IACK tries to send two datagrams for all 200 clients simultaneously, causing UDP socket drops and buffer contention. Static WFC forces all 200 clients to wait for the certificate delay. Load-Aware grants low-latency Instant ACKs to the first 8 arrivals, and smoothly throttles the remaining 192 into coalesced WFC flights, capturing low latency while protecting the socket buffer."*

#### Q3: "Why not just increase the server's UDP socket buffer instead of switching policies?"
> **Answer**: *"Increasing socket buffer size absorbs bursts but introduces **Bufferbloat**. Datagrams sit in massive kernel queues, delaying certificate flights and causing the client's tight PTO timer to expire anyway. Switching to single-flight coalesced WFC cuts system calls by 50% and addresses the root cause of queue congestion."*

#### Q4: "What is the primary architectural difference between Load-Aware v1 and v2?"
> **Answer**: *"v1 is reactive and uses a mutex-protected state transition (~150ns). v2 is lock-free (using atomic CAS registers running in $<5\text{ns}$) and predictive (it computes an EWMA arrival rate derivative $d\text{Load}/dt$ to switch to coalescing before the socket buffer fills)."*

#### Q5: "Why did the research paper require Go 1.20 specifically?"
> **Answer**: *"The upstream research fork uses `qtls-go1-20`, a customized TLS 1.3 stack that exposes internal session secrets and handshake hooks to QUIC. Since `qtls` patches the Go internal standard library's `crypto/tls`, it is pinned to the Go 1.20 memory layout."*

#### Q6: "Does Instant ACK violate RFC 9000 or RFC 9002?"
> **Answer**: *"No. RFC 9000 explicitly allows transmitting an `Initial` packet containing only an `ACK` frame. RFC 9002 specifies that the first received acknowledgment sets the initial RTT sample. Instant ACK is fully standard-compliant."*

#### Q7: "Does splitting the flight delay HTTP/3 application data?"
> **Answer**: *"No. As proven by our Time to First Byte (TTFB) measurements in Figure 2, TTFB is identical across all three policies across all RTTs. The client can only send application stream requests after receiving `ServerHello` and `HandshakeDone`, which occurs at the exact same point in time."*

#### Q8: "How does packet loss interact with the two policies?"
> **Answer**: *"In lossy networks, WFC is severely penalized because certificate delay $\Delta t$ inflates initial PTO ($\text{PTO} \approx 3 \times (\text{RTT} + \Delta t)$). Under 5% loss, WFC suffers a 328ms tail stall. Instant ACK and Load-Aware maintain true RTT calibration, recovering in 129.9ms—60.5% faster."*

#### Q9: "Why did 8 pegged CPU cores show less than 1ms difference in Experiment A.1?"
> **Answer**: *"Because Go's runtime scheduler efficiently multiplexes goroutines across execution cores, and low-concurrency QUIC handshakes consume negligible CPU. Protocol collapse is driven by UDP socket buffer queueing, lock contention, and `sendmsg` syscall volume under high connection concurrency, not raw external CPU compute."*

#### Q10: "What are your concrete plans for Milestone 3?"
> **Answer**: *"For Milestone 3, we plan to validate Load-Aware v2 across distributed wide-area Internet testbeds with remote clients, integrate kernel-level socket queue depth feedback using eBPF, and refine our arrival velocity pacing to publish our final v3 design."*

---

## ⚡ Quick Commands Reference

### 1. View PowerPoint Slides:
Open [`Load_Aware_QUIC_Instant_ACK_Presentation.pptx`](file:///b:/Mtech%20First%20Sem/Adv%20comp%20netw/Project/New%20folder/ACN_Presentation_Package/Load_Aware_QUIC_Instant_ACK_Presentation.pptx) in Microsoft PowerPoint. Press **F5** to enter presentation mode.

### 2. View Interactive Browser Presentation:
Double click [`presentation.html`](file:///b:/Mtech%20First%20Sem/Adv%20comp%20netw/Project/New%20folder/ACN_Presentation_Package/presentation.html) or open it in Google Chrome or Microsoft Edge.  
* Press **Space** or **Right Arrow** to advance.
* Press **S** to open the Speaker Notes drawer.
* Press **O** to open the 21-slide thumbnail grid.
* Press **F** for fullscreen presentation mode.

### 3. Launch Live Presentation Telemetry Dashboard:
```bash
# Terminal 1: Start the Load-Aware Server
./implementation/bin/server --mode=loadaware --addr=127.0.0.1:4433 --metrics-addr=127.0.0.1:8080

# Terminal 2: Launch Streamlit Dashboard
streamlit run implementation/dashboard/app.py
```
Open `http://localhost:8501` to view live gauges of active handshakes, policy transitions, and IACK/WFC ratios.
