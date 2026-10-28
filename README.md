# Load-Aware QUIC Instant ACK — Presentation Baseline Package

> **Course**: COL724 / COL7524: Advanced Computer Networks (IIT Delhi, Semester 1, 2026–27)  
> **Milestone 2**: Progress Presentation (October 28, 2026)  
> **Team**: Muhammed Nishad (2026MCS2799) & Ayush Arya (2026MCS2802)  
> **Base Paper**: *ReACKed QUICer: Measuring the Performance of Instant Acknowledgments in QUIC Handshakes* (ACM IMC 2024)

---

## ⚡ Quick Start: 3-Step Setup

### Step 1: Prerequisites
1. **Go 1.20+**: Verify by running `go version`.
   *(Note: The modified `quic-go` fork uses `qtls-go1-20` which requires a Go 1.20 toolchain).*
2. **Python 3**: For plotting and the live dashboard:
   ```bash
   pip install matplotlib pandas numpy streamlit
   ```

### Step 2: Compile the QUIC Binaries
From the root of this folder, compile the 3 core binaries:
```bash
cd implementation
go build -o bin/server cmd/server/main.go
go build -o bin/client cmd/client/main.go
go build -o bin/proxy cmd/proxy/main.go
cd ..
```
*(This builds the unified multi-mode server, the measurement client, and the UDP proxy network emulator).*

### Step 3: Launch the Real-Time Presentation Dashboard
Open two terminal tabs:

**Terminal 1 — Start the Load-Aware Server**:
```bash
./implementation/bin/server --mode=loadaware --addr=127.0.0.1:4433 --metrics-addr=127.0.0.1:8080
```

**Terminal 2 — Launch Streamlit Dashboard**:
```bash
streamlit run implementation/dashboard/app.py
```
Open your browser at `http://localhost:8501`. 
You can now view:
- **Live Server Monitor**: Real-time gauge of active handshakes, policy transitions, and IACK/WFC ratios.
- **Baseline Experiment Gallery**: All 8 high-resolution figures for tomorrow's presentation.
- **Architecture & Theory**: Quick reference on RFC 9002 PTO equations and the Schmitt-trigger hysteresis state machine.

---

## 📁 Package Contents

```
ACN_Presentation_Package/
├── artifacts-imc24-reACKed-QUICer/
│   └── 01-quic-go-instant-ack/     <-- Modified quic-go fork from IMC '24 paper
├── implementation/
│   ├── cmd/
│   │   ├── server/main.go          <-- Multi-mode QUIC server (wfc, iack, loadaware)
│   │   ├── client/main.go          <-- Measurement client (RTT, TTFB, t1-t4, PTOs)
│   │   └── proxy/main.go           <-- Asynchronous user-space UDP network emulator
│   ├── loadmonitor/
│   │   └── loadmonitor.go          <-- Schmitt-trigger hysteresis controller [4, 8]
│   ├── dashboard/
│   │   └── app.py                  <-- Real-time Streamlit web dashboard
│   ├── scripts/
│   │   ├── run_experiments.py      <-- Runs the 8 baseline experiments
│   │   └── generate_plots.py       <-- Generates Figures 1 through 8
│   ├── go.mod                      <-- Go module linking to modified quic-go
│   └── go.sum
├── figures/                        <-- The EXACT 8 baseline presentation plots:
│   ├── fig1_handshake_latency_vs_rtt.png
│   ├── fig2_ttfb_vs_rtt.png
│   ├── fig3_latency_under_load.png
│   ├── fig4_policy_decision_transition.png
│   ├── fig5_cert_delay_sweep_crossover.png
│   ├── fig6_phase_wait_time_breakdown.png
│   ├── fig7_threshold_sensitivity.png
│   └── fig8_winner_heatmap.png
├── data/                           <-- The 8 raw baseline CSV benchmark files
├── Paper.pdf                       <-- Original IMC 2024 paper (ReACKed QUICer)
├── Project_Guidelines.pdf          <-- IIT Delhi course project guidelines
├── CODE_AND_EXPERIMENT_GUIDE.md    <-- Detailed pedagogical guide with code walkthrough
└── PROJECT_README.md               <-- Comprehensive research report and slides mapping
```

---

## 📊 How to Re-Run the Baseline Experiments (Optional)

All 8 figures and raw datasets are **already pre-generated and included** in `figures/` and `data/`. If you want to re-run the benchmarks from scratch:

```bash
# 1. Run all 8 experiments across WFC, IACK, and Load-Aware:
python3 implementation/scripts/run_experiments.py

# 2. Re-render publication figures 1 to 8:
python3 implementation/scripts/generate_plots.py
```

---

