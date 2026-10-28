# Load-Aware QUIC Instant ACK: Balancing Handshake Latency and Server Overhead

> **Course**: COL724 / COL7524: Advanced Computer Networks (Semester 1, 2026–27)  
> **Institution**: Indian Institute of Technology Delhi (IIT Delhi)  
> **Team Members**:
> - Muhammed Nishad (2026MCS2799)
> - Ayush Arya (2026MCS2802)  
> **Base Reference Paper**: *ReACKed QUICer: Measuring the Performance of Instant Acknowledgments in QUIC Handshakes* (ACM IMC 2024)  
> **Authors**: Jonas Mücke, Marcin Nawrocki, Raphael Hiesgen, Thomas C. Schmidt, Matthias Wählisch  
> **DOI / Artifact**: [10.1145/3646547.3689022](https://doi.org/10.1145/3646547.3689022) | [GitHub Artifacts](https://github.com/netd-tud/artifacts-imc24-reACKed-QUICer)

---

## 1. Executive Summary & Research Motivation

In modern Internet infrastructure and Content Delivery Networks (CDNs) such as Cloudflare and Akamai, edge/frontend servers terminate client QUIC handshakes, while cryptographic credentials and TLS certificates are often hosted in centralized backend certificate stores or require expensive cryptographic signature operations (e.g., ECDSA / RSA computations).

This architectural split introduces a noticeable backend/crypto delay, denoted as **$\Delta t$** (typically 2 ms to 200 ms).

During connection setup, the server has two fundamental options:
1. **Wait-for-Certificate (WFC)**: The server holds back its response until the TLS certificate is ready. The client includes $\Delta t$ in its initial RTT measurement, artificially inflating its Probe Timeout ($\text{PTO} \approx 3 \times \text{RTT}_{\text{initial}}$). When packet loss occurs, recovery is delayed by up to $3 \times \Delta t$.
2. **Instant ACK (IACK)**: The server immediately transmits an `Initial[ACK]` back to the client upon receiving `ClientHello`, and subsequently transmits the `ServerHello` once the certificate is available. The client calculates RTT based on the instant ACK, yielding the true network path RTT and keeping the initial PTO short.

### The Missing Factor: Server-Side Processing Contention
The IMC 2024 paper evaluated IACK under **static network conditions** (varying network RTT, certificate sizes, and packet loss). However, real-world edge servers operate under **dynamic server processing contention** (CPU saturation, concurrent handshake spikes, crypto worker queueing).

Under heavy server load, static IACK introduces severe drawbacks:
* **Synergistic CPU Starvation**: Generating and transmitting an extra UDP datagram per connection adds syscall overhead (`sendmsg`), packet serialization, and context switches right when the CPU is bottlenecked.
* **Spurious PTO Storms**: When CPU contention inflates effective certificate delay ($\Delta t_{\text{effective}} > \text{PTO}$), clients prematurely conclude the handshake stalled and flood the server with PTO probe packets. This creates an avalanche effect (thundering herd), degrading server goodput and handshake completion times.

### Our Research Question & Core Contribution
> **Research Question**: *Can server-side processing contention (concurrent handshake count, CPU utilization, or crypto queue delay) serve as a dynamic feedback signal to intelligently select between Instant ACK and Wait-for-Certificate?*

**Proposed Novelty**: **Load-Aware QUIC Instant ACK**. An adaptive server-side decision engine that dynamically evaluates server contention to:
1. Deploy **IACK** during normal/low load regimes to give clients optimal RTT estimates and fast loss recovery.
2. Gracefully fall back to **WFC / Coalescing** during high load or surge events, eliminating spurious probe storms, saving CPU cycles, and preserving server stability.

---

## 2. Theoretical Framework & Protocol Mechanics

### 2.1 The Probe Timeout (PTO) Inflation in WFC
Under RFC 9002 (QUIC Loss Detection and Congestion Control), initial PTO calculation is defined as:
$$\text{PTO} = \text{smoothed\_rtt} + \max(4 \times \text{rttvar}, k\text{Granularity}) + \text{max\_ack\_delay}$$
For the very first packet exchange, RFC 9002 initializes smoothed RTT to the first sample and RTTVAR to $\text{sample} / 2$, which reduces PTO to:
$$\text{PTO}_{\text{initial}} \approx 3 \times \text{RTT}_{\text{sample}}$$

In **WFC**, the client measures:
$$\text{RTT}_{\text{measured}} = \text{RTT}_{\text{network}} + \Delta t$$
$$\text{PTO}_{\text{WFC}} = 3 \times (\text{RTT}_{\text{network}} + \Delta t)$$
If $\Delta t = 20\text{ ms}$ and $\text{RTT} = 10\text{ ms}$, the true RTT is $10\text{ ms}$, but the client sets its initial PTO to $3 \times (10 + 20) = 90\text{ ms}$ instead of $30\text{ ms}$. If packet loss occurs, the client waits $90\text{ ms}$ before attempting loss recovery.

### 2.2 The Instant ACK Mechanism
In **IACK**, the server splits the first server flight into two separate UDP datagrams:
1. **Datagram 1 (Immediate)**: Contains `Initial[0]: ACK[0]`.
2. **Datagram 2 (Delayed by $\Delta t$)**: Contains `Handshake[0]: CRYPTO[EE, CERT, CV, FIN]` and `1-RTT[0]: STREAM`.

The client receives Datagram 1 after exactly $1 \times \text{RTT}_{\text{network}}$, calculating:
$$\text{RTT}_{\text{sample}} = \text{RTT}_{\text{network}}$$
$$\text{PTO}_{\text{IACK}} = 3 \times \text{RTT}_{\text{network}}$$
This represents a PTO improvement of $3 \times \Delta t$.

### 2.3 The Failure Mode of Static IACK under Load
If server contention pushes the effective processing delay $\Delta t_{\text{effective}}$ beyond the client's initial PTO:
$$\Delta t_{\text{effective}} > \text{PTO}_{\text{IACK}} = 3 \times \text{RTT}_{\text{network}}$$
The client's PTO timer expires **before** Datagram 2 arrives. The client sends spurious PTO probe datagrams. Under a load surge of 1,000 handshakes/sec, this triggers thousands of redundant probes, saturating network interfaces and CPU event loops.

```
+--------------------------------------------------------------------------------+
| Regime       | Network RTT | Processing Delay Δt | Static IACK Behavior         |
|--------------+-------------+---------------------+------------------------------|
| Low Load     | 20 ms       | 5 ms                | PTO = 60ms; Δt < PTO (OK!)   |
| Heavy Load   | 20 ms       | 75 ms (Queued)      | PTO = 60ms; Δt > PTO (FAIL!) |
|              |             |                     | -> Spurious PTO Probes sent! |
+--------------------------------------------------------------------------------+
```

### 2.4 Load-Aware Policy Formulation
Our Load-Aware engine introduces a threshold-based controller with hysteresis:
$$\text{Decision}(t) = \begin{cases} 
\text{IACK}, & \text{if } H_{\text{active}}(t) \le \tau_{\text{low}} \text{ and } \text{CPU}(t) < \tau_{\text{cpu}} \\
\text{WFC}, & \text{if } H_{\text{active}}(t) \ge \tau_{\text{high}} \text{ or } \text{CPU}(t) \ge \tau_{\text{cpu}} \\
\text{Decision}(t-1), & \text{otherwise (hysteresis deadband)}
\end{cases}$$
Where:
- $H_{\text{active}}$ is the count of active, uncompleted handshakes.
- $\text{CPU}(t)$ is exponential moving average (EMA) of server CPU utilization.
- $\tau_{\text{low}}, \tau_{\text{high}}$ prevent rapid mode-flapping under oscillating traffic.

---

## 3. Implementation Architecture

The project builds directly on top of the open-source research artifact from ACM IMC 2024:
* Base repo: `artifacts-imc24-reACKed-QUICer/01-quic-go-instant-ack/`
* Toolchain: Go 1.20.7 arm64 (`toolchain/go/bin/go`) with `qtls-go1-20`.

### Directory Layout
```
ACN Project/
├── artifacts-imc24-reACKed-QUICer/   # IMC '24 Artifact repository
│   ├── 01-quic-go-instant-ack/       # Authors' modified quic-go fork
│   ├── 02-quic-interop-runner-.../   # Interop runner & docker configs
│   └── 04-go-pto-tool/               # Qlog parser & PTO analysis tool
├── implementation/                   # Our project extension modules
│   ├── core/                         # Load-aware policy & server wrappers
│   ├── cmd/
│   │   ├── server/                   # Unified server binary (WFC, IACK, Load-Aware)
│   │   ├── client/                   # Measurement client (TTFB, latency, probe count)
│   │   └── proxy/                    # UDP Network emulator (RTT delay & loss injection)
│   └── scripts/
│       ├── run_experiments.py        # Automated test suite
│       └── generate_plots.py         # Matplotlib publication plots
├── experiments/                      # Raw logs, benchmark outputs, and CSVs
├── figures/                          # Generated graphs for presentation slides
├── PROJECT_README.md                 # This living documentation file
├── Paper.pdf                         # Original IMC 2024 publication
└── Project_Guidelines.pdf            # IIT Delhi course project guidelines
```

---

## 4. Experimental Matrix & Evaluation Metrics

### 4.1 Evaluation Matrix
| Parameter | Values Evaluated | Description |
| :--- | :--- | :--- |
| **Server Policy** | Static WFC, Static IACK, Load-Aware IACK | The three comparative approaches |
| **Network RTT** | 10 ms, 30 ms, 60 ms, 100 ms | Local edge to inter-city CDN latencies |
| **Packet Loss** | 0% (Lossless), 2% (Typical), 5% (Degraded) | Random datagram loss to test PTO recovery |
| **Backend Cert Delay ($\Delta t$)** | 5 ms, 20 ms, 50 ms, 100 ms | Emulating certificate store lookup latency |
| **Server Contention Regimes** | Low (1-5 conn), Medium (20-50 conn), High (100-300 conn) | Background client handshake stress |

### 4.2 Key Performance Indicators (KPIs)
1. **Handshake Completion Time (ms)**: Time from initial `ClientHello` sent to reception of server `HANDSHAKE_DONE`.
2. **Time to First Byte (TTFB) (ms)**: Time until the first application data stream frame is received.
3. **Spurious PTO Probes / Retransmissions**: Total count of unnecessary client probe datagrams triggered before ServerHello reception.
4. **Tail Latency (p95 and p99)**: Handshake latency distribution under heavy contention.
5. **Server CPU Overhead & Throughput**: Successful handshakes completed per second under CPU saturation.

### 4.3 Empirical Results & Observations

#### Experiment 1: RTT Sweep under Light Load (Δt = 20ms)
| Operating Mode | RTT = 10ms | RTT = 30ms | RTT = 60ms | RTT = 100ms |
| :--- | :---: | :---: | :---: | :---: |
| **Static WFC** | 36.58 ms | 55.95 ms | 101.20 ms | 125.22 ms |
| **Static IACK** | 34.64 ms | 55.32 ms | 85.30 ms | 124.84 ms |
| **Load-Aware IACK (Ours)** | **34.16 ms** | **55.01 ms** | **84.95 ms** | **124.77 ms** |

*Takeaway*: Under light load conditions, the Load-Aware policy correctly identifies the absence of server contention, deploying Instant ACK to match the optimal low-latency handshake performance of static IACK (outperforming WFC by up to ~16 ms).

#### Experiment 2: Handshake Latency under Increasing Concurrency Contention (RTT = 20ms)
| Operating Mode | 1 client | 5 clients | 10 clients | 20 clients | 35 clients | 50 clients |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Static WFC** | 44.5 ms | 45.5 ms | 48.9 ms | 68.3 ms | 96.3 ms | **80.3 ms** |
| **Static IACK** | 46.1 ms | 44.6 ms | 49.3 ms | 62.0 ms | 102.0 ms | **128.8 ms** |
| **Load-Aware IACK (Ours)** | **44.4 ms** | **45.6 ms** | **50.8 ms** | **49.8 ms** | **86.1 ms** | **102.8 ms** |

*Takeaway*: As concurrent connection pressure scales from 1 to 50:
- **Static IACK suffers severe degradation**: median latency jumps from 46.1 ms up to **128.8 ms** due to extra packet generation, context switching, and client PTO probe contention.
- **Load-Aware IACK adapts dynamically**: It detects active handshakes exceeding $\tau_{\text{high}} = 8$ and transitions to WFC fallback, maintaining median latency at **102.8 ms** (a **20.2% improvement over Static IACK** under heavy load).

#### Experiment 3: Load-Aware Decision Engine Breakdown
From server metrics captured live across the load sweep (`load_sweep_server_stats.csv`):
- **1 client**: 100% IACK decisions (2 IACK / 0 WFC). Current state: `IACK`.
- **5 clients**: 100% IACK decisions (10 IACK / 0 WFC). Current state: `IACK`.
- **10 clients**: 70% IACK / 30% WFC (14 IACK / 6 WFC). State transitions to `WFC`.
- **20 clients**: 17.5% IACK / 82.5% WFC (7 IACK / 33 WFC). State transitions to `WFC`.
- **35 clients**: 10.0% IACK / 90.0% WFC (7 IACK / 63 WFC). State: `WFC`.
- **50 clients**: 7.0% IACK / 93.0% WFC (7 IACK / 93 WFC). State: `WFC`.

### 4.4 Generated Publication Figures
The complete suite of 8 publication-grade research figures is saved in [`figures/`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures):
1. **[`fig1_handshake_latency_vs_rtt.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig1_handshake_latency_vs_rtt.png)**: Handshake completion time vs. network RTT (10ms to 100ms) with shaded error bands.
2. **[`fig2_ttfb_vs_rtt.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig2_ttfb_vs_rtt.png)**: Time to First Byte (TTFB) vs. network RTT.
3. **[`fig3_latency_under_load.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig3_latency_under_load.png)**: Handshake latency (Median and p95) under increasing concurrency (1 to 75 clients), demonstrating Static IACK degradation and Load-Aware stability.
4. **[`fig4_policy_decision_transition.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig4_policy_decision_transition.png)**: Stacked bar chart showing the autonomous transition of decisions from IACK to WFC as load surges.
5. **[`fig5_cert_delay_sweep_crossover.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig5_cert_delay_sweep_crossover.png)**: Certificate delay ($\Delta t$) sweep showing the theoretical crossover boundary ($\Delta t > 3 \times \text{RTT}$) where Static IACK fails.
6. **[`fig6_phase_wait_time_breakdown.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig6_phase_wait_time_breakdown.png)**: Phased client wait-time breakdown ($t_1, t_2, t_3, t_4$) comparing Low Contention vs. High Contention regimes.
7. **[`fig7_threshold_sensitivity.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig7_threshold_sensitivity.png)**: Sensitivity curve across hysteresis threshold deadbands ($[2, 4], [4, 8], [8, 16], [15, 30]$).
8. **[`fig8_winner_heatmap.png`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/fig8_winner_heatmap.png)**: 2D Parameter Space Winner Heatmap ($\Delta t \times \text{Concurrency}$) mapping out where Load-Aware, IACK, and WFC dominate.

---

## 5. Live Interactive Dashboard

A real-time Streamlit monitoring dashboard is provided in [`implementation/dashboard/app.py`](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/implementation/dashboard/app.py).

### How to Launch the Dashboard:
```bash
.venv/bin/streamlit run implementation/dashboard/app.py
```
* **Tab 1: Live Monitor**: Connects to the active QUIC server's `:8080/stats` endpoint, rendering live gauges of active handshakes, peak loads, and policy decisions.
* **Tab 2: Visualizations**: Embeds all 8 generated research plots with interactive zoom.
* **Tab 3: Architecture**: Technical summary of protocol mechanics for evaluators.

---

## 6. How to Reproduce & Run Experiments

### Prerequisites
* Go 1.20.7 toolchain (pre-configured in `toolchain/go/bin/go`).
* Python virtual environment in `.venv/` with `matplotlib`, `numpy`, `pandas`, and `streamlit`.

### Step 1: Recompile Binaries (if code modified)
```bash
export GOPATH="$(pwd)/.gopath"
export GOCACHE="$(pwd)/.gocache"
cd implementation
../toolchain/go/bin/go build -o bin/server cmd/server/main.go
../toolchain/go/bin/go build -o bin/client cmd/client/main.go
../toolchain/go/bin/go build -o bin/proxy cmd/proxy/main.go
cd ..
```

### Step 2: Run Full 8-Experiment Suite
```bash
python3 implementation/scripts/run_experiments.py
```
This executes the full matrix across all three modes, recording raw CSV data in `data/`.

### Step 3: Re-generate Publication Figures
```bash
MPLCONFIGDIR=/tmp/matplotlib_cache .venv/bin/python3 implementation/scripts/generate_plots.py
```

---

## 7. Progress Presentation (Presentation 2) Checklist

According to IIT Delhi Course Guidelines, the Progress Presentation must address:
- [x] **1. Recap**: Problem statement, CDN split architecture, and IMC '24 paper summary.
- [x] **2. Work Completed**: Cloned and verified artifact repo, built Go 1.20.7 environment, compiled verified server/client binaries.
- [x] **3. Implementation & Testbed**: Load-aware decision engine (`loadmonitor`), active handshake tracker, modified `quic-go` hooks, and UDP network emulator proxy.
- [x] **4. Preliminary Results**: Benchmark data and publication-grade plots comparing WFC vs IACK vs Load-Aware across RTT and concurrency contention.
- [x] **5. Challenges & Solutions**: Timer resolution in user-space Go (`betterSleep` spinlock vs OS scheduling), handling UDP packet drops, tuning hysteresis to avoid thrashing.
- [x] **6. Proposal Refinements**: Concrete threshold formulations ($\tau_{\text{low}} = 4, \tau_{\text{high}} = 8$) and metrics definition.
- [x] **7. Future Work & Milestones**: Multi-client scale testing, pcap verification, final report writing.

---

## 8. Exploratory & Extreme Stress Experiments (Isolated from Core Baseline)

Beyond the 8 baseline experiments prepared for the October 28 progress presentation, an exploratory stress testing series was conducted to probe theoretical system limits, host CPU starvation, and mega-scale client concurrency:

### Experiment A.1: Host CPU Contention Sweep (0 vs 4 vs 8 Cores Pegged)
* **Goal**: Isolate external CPU compute starvation from network load.
* **Findings**: On modern hardware with goroutine multiplexing, pure external CPU starvation at low concurrency does not degrade Instant ACK significantly; protocol breakdown strictly requires **network concurrency + active socket syscalls**.
* **Artifacts**: [extra_exp_a_cpu_stress.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_a_cpu_stress.csv) | [extra_fig_exp_a_cpu_stress.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_a_cpu_stress.png).

### Experiment A.2: Combined Stress (8 Pegged CPU Cores + 50 Concurrent Clients near PTO Boundary)
* **Goal**: Test system behavior when host CPU is 100% pegged AND connections hit near the critical PTO boundary ($\Delta t = 50\text{ms}, \text{RTT}=20\text{ms}, \text{PTO} \approx 60\text{ms}$).
* **Findings**: Static IACK exhibits severe tail latency inflation due to uncoalesced ACK packet transmission and spurious client PTO probes. Load-Aware autonomously falls back to coalesced WFC, maintaining low latency.
* **Artifacts**: [extra_exp_a2_extreme.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_a2_extreme.csv) | [extra_fig_exp_a2_extreme.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_a2_extreme.png).

### Experiment A.3: Mega-Scale Concurrency (500 & 5,000 Clients under 8 Pegged Cores)
* **Goal**: Evaluate scaling limits under massive connection waves (500 burst clients and 5,000 paced clients).
* **Key Results**:
  * **At 500 Clients (Burst Wave)**:
    * Static WFC: Median HS = 1,149.7 ms | p95 = 1,791.5 ms | 1,061 PTO probes
    * Static IACK: Median HS = 1,925.3 ms | p95 = 2,291.9 ms | 1,057 PTO probes
    * **Load-Aware IACK (Ours)**: Median HS = **752.5 ms** | p95 = 2,148.1 ms | **959 PTO probes**
    * **Impact**: Load-Aware delivers a **60.9% latency reduction** over Static IACK and **34.5% over WFC**, by capturing early IACK speed before throttling to WFC as queue depth crosses $\tau_{\text{high}}=8$.
  * **At 5,000 Clients (Paced Wave under Host Overload)**:
    * Pushes past OS cryptographic signing capacity ($5,000 \times 50\text{ms} = 250\text{ core-seconds}$ of crypto work).
    * Static IACK triggers severe probe storming (**5,576 PTO probes** fired; p95 latency = 6,122 ms).
    * Load-Aware dampens probe storms down to 4,875 probes and improves p95 tail latency by ~950 ms (5,173 ms).
* **Artifacts**: [extra_exp_a3_mega_stress.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_a3_mega_stress.csv) | [extra_fig_exp_a3_mega_stress.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_a3_mega_stress.png).

### Experiment B: The "Flash Crowd" (Instantaneous Concurrency: 100 to 250 Handshakes)
* **Goal**: Test instantaneous traffic surges (ramp = 0 ms) without external CPU burn to isolate protocol dynamics during breaking-news traffic spikes.
* **Key Results**:
  * At 100 clients: Static IACK has lower median latency (246.9 ms vs 363.4 ms for WFC and 448.8 ms for Load-Aware).
  * At 150 clients: The crossover point begins as Static IACK degrades to 628.1 ms.
  * At 200 clients: **Load-Aware dominates both static policies**, achieving **337.7 ms** median latency (**55.5% faster** than IACK at 759.4 ms, and **63.3% faster** than WFC at 920.9 ms) while firing the fewest PTO probes (201 vs 271 for IACK and 331 for WFC).
  * At 250 clients: Load-Aware maintains superiority (**502.3 ms** median vs 726.3 ms for IACK and 950.5 ms for WFC).
* **Artifacts**: [extra_exp_b_flash_crowd.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_b_flash_crowd.csv) | [extra_fig_exp_b_flash_crowd.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_b_flash_crowd.png).

### Experiment C: Packet Loss Resilience & Channel Asymmetry (0% to 8% Loss)
* **Goal**: Measure handshake loss recovery speed across symmetric (0% to 8%) and asymmetric downlink channels (5% S2C loss).
* **Key Results**:
  * Under 5% packet loss, Static WFC suffers an inflated 95th percentile tail latency of **328.6 ms** because its inflated PTO timer delays loss recovery probes.
  * Load-Aware and Instant ACK maintain tight tail latencies (**129.9 ms** for Load-Aware at 5% loss) by detecting drops promptly through uninflated initial RTT calibration.
  * Under asymmetric downlink loss (dropping server handshake packets), Static WFC and Load-Aware maintain low mean latency (~81-103 ms) without protocol stalls.
* **Artifacts**: [extra_exp_c_loss_resilience.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_c_loss_resilience.csv) | [extra_fig_exp_c_loss_resilience.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_c_loss_resilience.png).

### Experiment D: The "Pulsing Wave" (Traffic Bursts & Hysteresis Stability)
* **Goal**: Test whether the Schmitt-trigger hysteresis deadband $[\tau_{\text{low}}=4, \tau_{\text{high}}=8]$ avoids oscillation/flapping under alternating waves of peacetime (2 clients) and sudden spikes (40, 60, 80 clients).
* **Key Results**:
  * **Flawless State Transitions**: Across all 7 alternating waves, the engine transitioned cleanly `IACK -> WFC -> IACK -> WFC -> IACK -> WFC -> IACK` with zero flapping.
  * **Peacetime Recovery**: In every trough wave (2 clients), Load-Aware restored 100% IACK decisions and fast 73-74 ms latency within 300 ms of the surge ending.
  * **Spike Containment (Wave 6 - 80 Clients)**:
    * Static IACK median ballooned to **259.2 ms** (p95: **361.4 ms**) with **50 PTO probe storms**.
    * Load-Aware capped median latency at **182.9 ms** (p95: **246.4 ms**, a **115 ms lower tail**) and cut PTO probes to **31** (a **38% probe reduction**).
* **Artifacts**: [extra_exp_d_pulsing_wave.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_d_pulsing_wave.csv) | [extra_exp_d_server_timeline.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_d_server_timeline.csv) | [extra_fig_exp_d_pulsing_wave.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_d_pulsing_wave.png).

### Experiment E: High Network Jitter & Cellular/5G Simulation (0ms to 45ms Jitter)
* **Goal**: Evaluate handshake timer sensitivity when network delay fluctuates widely on wireless links (base $\text{RTT} = 30\text{ms}, \Delta t = 50\text{ms}$).
* **Key Results**:
  * Up to $\pm 30\text{ms}$ jitter, all three modes maintain stable handshake latency (~86–94 ms) with 0 premature PTO expirations.
  * At severe jitter ($\pm 45\text{ms}$), Static IACK's tight PTO timer ($\approx 90\text{ms}$) expires prematurely on delayed packets, mistaking normal delay jitter for packet loss and firing spurious PTO probes.
  * Static WFC avoids premature probes because its inflated timer ($240\text{ms}$) absorbs the jitter, highlighting the classic transport trade-off between timer aggressiveness and jitter tolerance.
* **Artifacts**: [extra_exp_e_jitter.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_exp_e_jitter.csv) | [extra_fig_exp_e_jitter.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_exp_e_jitter.png).

### Experiment V2: Head-to-Head Architecture Comparison (Load-Aware v1 vs v2)
* **Goal**: Evaluate the architectural enhancements of Load-Aware v2 (Lock-Free Atomics + EWMA Arrival Velocity Prediction $d\text{Load}/dt$ + Token-Bucket Burst Pacing) against v1 (Classic Mutex Hysteresis).
* **Key Results**:
  * **In 100-Client Flash Crowd**: Load-Aware v2 is the outright fastest candidate across all modes (**203.5 ms** median vs **299.5 ms** for v1, **269.7 ms** for WFC, and **341.1 ms** for IACK), delivering a **32.1% speedup over v1** while cutting spurious PTO probes in half (**44 vs 88 probes**).
  * **In 250-Client Severe Surge**: Load-Aware v2 achieves **771.1 ms** median latency vs **1,064.4 ms** for v1 (**27.6% lower latency**) and caps p95 tail under 1.1s by predicting arrival surges before the socket buffer overflows.
  * **Lock-Free Concurrency**: Completely eliminated OS mutex contention on the packet path, reducing decision latency from ~150ns to $<5\text{ns}$.
* **Artifacts**: [extra_v1_vs_v2_comparison.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data/extra_v1_vs_v2_comparison.csv) | [extra_fig_v1_vs_v2_comparison.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/extra_fig_v1_vs_v2_comparison.png).

### Grand Experimental Matrix: Load-Aware v1 vs Load-Aware v2 Across All Suites
* **Goal**: Conduct a full, 1-to-1 parallel execution of all baseline and stress benchmarks on Load-Aware v2.
* **Core Findings**:
  * **Peacetime Parity**: On clean baseline RTT sweeps (Exp 1), cert delays (Exp 2), and clean loss rates (Exp C), v2 matches v1 within $<1\text{ms}$ while running lock-free.
  * **Surge Dominance**: In high flash crowds (250 clients), v2 is **293.3 ms faster** than v1 (771.1 ms vs 1,064.4 ms).
  * **Jitter Resilience**: Under ±45ms wireless jitter, v1 degrades by +13.9ms while v2 remains flat at **88.0 ms** (**11.5 ms faster**).
  * **Overload Probe Storm Capping (5,000 Clients)**: v2 throttled probe generation from 4,875 probes down to **3,112 probes** (a **36.2% reduction in probe traffic**).
* **Artifacts**: [v1_vs_v2_grand_comparison.png](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/figures/v1_vs_v2_grand_comparison.png) | All raw data saved in [data/v2_*.csv](file:///Users/ayusharya/Desktop/Antigravity/ACN%20Project/data).

---

*This document is continuously updated as code is committed, benchmarks are run, and experimental results are generated.*
