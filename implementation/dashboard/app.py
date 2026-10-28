import streamlit as st
import json
import time
import urllib.request
import os
import pandas as pd

st.set_page_config(page_title="Load-Aware QUIC Dashboard", layout="wide", page_icon="⚡")

METRICS_URL = "http://127.0.0.1:8080/stats"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
DATA_DIR = os.path.join(BASE_DIR, "data")

# Sidebar Navigation
st.sidebar.title("⚡ QUIC Dashboard")
st.sidebar.markdown("**IIT Delhi — COL724/COL7524**\n*Advanced Computer Networks*")
st.sidebar.divider()

nav = st.sidebar.radio(
    "Go to",
    ["🔴 Live Server Monitor", "📊 Baseline Experiment Gallery (Core)", "📖 Architecture & Theory"],
    index=0
)

st.sidebar.divider()
st.sidebar.caption("Project: Muhammed Nishad & Ayush Arya")

def fetch_stats():
    try:
        req = urllib.request.urlopen(METRICS_URL, timeout=1)
        return json.loads(req.read().decode())
    except Exception:
        return None

# ==============================================================================
# TAB 1: LIVE SERVER MONITOR
# ==============================================================================
if nav == "🔴 Live Server Monitor":
    st.title("🔴 Live QUIC Server Contention Monitor")
    st.markdown("Real-time monitoring of server-side active handshakes, decision engine state, and dynamic policy transitions.")

    col_ctrl1, col_ctrl2 = st.columns([3, 1])
    with col_ctrl1:
        st.caption(f"Connected to local QUIC server at `{METRICS_URL}`")
    with col_ctrl2:
        auto_refresh = st.checkbox("Auto-refresh live stream (2s)", value=False)
        if st.button("🔄 Refresh Now"):
            st.rerun()

    stats = fetch_stats()

    if stats is not None:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Active Handshakes", stats.get("active_handshakes", 0))
        m2.metric("Peak Handshakes", stats.get("peak_handshakes", 0))
        m3.metric("Total Completed", stats.get("total_completed", 0))
        cur_mode = stats.get("current_state", "N/A")
        m4.metric("Current Policy Mode", cur_mode, delta="Fast PTO" if cur_mode == "IACK" else "Throttling")
        m5.metric("IACK / WFC Ratio", f"{stats.get('iack_decisions', 0)} / {stats.get('wfc_decisions', 0)}")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Policy Decision Distribution")
            iack_cnt = stats.get("iack_decisions", 0)
            wfc_cnt = stats.get("wfc_decisions", 0)
            if iack_cnt + wfc_cnt > 0:
                df_decisions = pd.DataFrame({
                    "Policy Strategy": ["Instant ACK (IACK)", "Wait-for-Certificate (WFC)"],
                    "Decisions": [iack_cnt, wfc_cnt]
                })
                st.bar_chart(df_decisions.set_index("Policy Strategy"), color="#2ca02c")
            else:
                st.info("No handshake decisions made yet. Send client requests to see live data.")

        with c2:
            st.markdown("### Hysteresis Contention Gauge")
            active = stats.get("active_handshakes", 0)
            st.write(f"**Current Contention Level:** {active} active handshakes")
            st.progress(min(1.0, active / 20.0))
            st.caption("Low Threshold: 4 | High Threshold: 8 (Deadband prevents mode-flapping)")

    else:
        st.warning(f"⚠️ Live QUIC server is currently offline or unreachable at `{METRICS_URL}`.")
        st.info("💡 **To start the server, open a terminal and run:**\n"
                "```bash\n"
                "./implementation/bin/server --mode=loadaware --addr=127.0.0.1:4433 --metrics-addr=127.0.0.1:8080\n"
                "```\n"
                "Then send client handshakes with:\n"
                "```bash\n"
                "./implementation/bin/client --target=127.0.0.1:4433 --concurrency=20 --requests=3\n"
                "```")

    st.divider()
    st.subheader("📁 Latest Recorded Experiment Server Stats (Exp 3)")
    stats_csv = os.path.join(DATA_DIR, "exp3_load_server_stats.csv")
    if os.path.exists(stats_csv):
        df_hist = pd.read_csv(stats_csv)
        df_la = df_hist[df_hist["mode"] == "loadaware"]
        c_hist1, c_hist2 = st.columns(2)
        with c_hist1:
            st.markdown("#### Decision Breakdown vs Concurrency")
            df_chart = df_la[["concurrency", "iack_decisions", "wfc_decisions"]].set_index("concurrency")
            st.bar_chart(df_chart, color=["#2ca02c", "#1f77b4"])
            st.caption("Green: IACK (Headroom) | Blue: WFC Fallback (Contention Protection)")
        with c_hist2:
            st.markdown("#### Peak Handshakes Scaled up to 75 Clients")
            st.line_chart(df_la.set_index("concurrency")[["active_peak"]], color="#ff7f0e")

    if auto_refresh:
        time.sleep(2)
        st.rerun()

# ==============================================================================
# TAB 2: BASELINE EXPERIMENT GALLERY (CORE)
# ==============================================================================
elif nav == "📊 Baseline Experiment Gallery (Core)":
    st.title("📊 Core Research Evaluation & Figures (Baseline)")
    st.markdown("Comprehensive evaluation across 8 experiments comparing **Static WFC**, **Static IACK**, and **Load-Aware IACK**.")

    figures = [
        ("fig1_handshake_latency_vs_rtt.png", "Figure 1: Handshake Latency vs. Network RTT",
         "Under light load, Load-Aware reliably chooses Instant ACK, matching the low latency of static IACK and outperforming WFC by up to ~16 ms across all RTTs."),
        ("fig2_ttfb_vs_rtt.png", "Figure 2: Time to First Byte (TTFB) vs. Network RTT",
         "Time to First Byte scales linearly with round-trip time, confirming consistent 1-RTT application delivery without protocol stalls."),
        ("fig3_latency_under_load.png", "Figure 3: Latency under Increasing Server Contention",
         "The Core Thesis: Static IACK latency balloons to 128+ ms at 50-75 concurrent handshakes. Load-Aware detects the surge, autonomously switches to WFC fallback, and caps latency at ~102 ms (a 20.2% improvement)."),
        ("fig4_policy_decision_transition.png", "Figure 4: Autonomous Policy Decision Transition",
         "Stacked bar chart showing the transition from 100% IACK decisions at low load to 93%+ WFC fallback under high concurrency surges."),
        ("fig5_cert_delay_sweep_crossover.png", "Figure 5: Certificate Delay Δt Sweep & PTO Crossover",
         "Demonstrates the theoretical boundary where Δt > 3 × RTT (120ms at RTT=40ms). Beyond this threshold, Static IACK induces premature PTO expirations and spurious retransmissions."),
        ("fig6_phase_wait_time_breakdown.png", "Figure 6: Client Handshake Phased Wait-Time Breakdown (t1 to t4)",
         "Deconstructs handshake duration into 4 distinct phases: t1 (Initial packet to 1st server packet), t2 (gap until cert arrival), t3 (handshake completion), and t4 (TTFB). Visualizes why IACK suffers high t2 under load."),
        ("fig7_threshold_sensitivity.png", "Figure 7: Hysteresis Threshold Sensitivity Analysis",
         "Tests threshold deadbands [(2,4), (4,8), (8,16), (15,30)]. Confirms that [4, 8] provides the ideal trade-off between rapid responsiveness and preventing rapid mode-flapping."),
        ("fig8_winner_heatmap.png", "Figure 8: 2D Headline Parameter Heatmap (Winner Map)",
         "2D parameter space mapping Δt (10ms-100ms) vs. Concurrency (1-50 clients). Shows the exact operational regimes where Load-Aware, IACK, and WFC dominate."),
    ]

    for fname, title, description in figures:
        fpath = os.path.join(FIGURES_DIR, fname)
        st.subheader(title)
        st.markdown(f"*{description}*")
        if os.path.exists(fpath):
            st.image(fpath, use_container_width=True)
        else:
            st.error(f"Image not found at `{fpath}`. Run `python3 implementation/scripts/generate_plots.py` to generate it.")
        st.divider()

# ==============================================================================
# TAB 3: ARCHITECTURE & THEORY
# ==============================================================================
elif nav == "📖 Architecture & Theory":
    st.title("📖 System Architecture & Theoretical Framework")

    st.markdown(r"""
    ### 1. Research Overview
    * **Course**: COL724 / COL7524: Advanced Computer Networks (Semester 1, 2026–27)
    * **Institution**: Indian Institute of Technology Delhi (IIT Delhi)
    * **Team**: Muhammed Nishad (2026MCS2799) & Ayush Arya (2026MCS2802)
    * **Base Paper**: *ReACKed QUICer: Measuring the Performance of Instant Acknowledgments in QUIC Handshakes* (ACM IMC 2024)
    * **DOI**: [10.1145/3646547.3689022](https://doi.org/10.1145/3646547.3689022)

    ---

    ### 2. The Core Problem
    In CDN architectures (e.g., Cloudflare, Akamai), edge servers terminate client QUIC handshakes, but TLS certificates must be retrieved from backend stores, introducing a delay $\Delta t$.
    * **Wait-for-Certificate (WFC)**: The server delays its response until the certificate is ready. The client includes $\Delta t$ in its initial RTT measurement, artificially inflating its Probe Timeout ($\text{PTO} \approx 3 \times \text{RTT}_{\text{initial}}$). Loss recovery is delayed.
    * **Instant ACK (IACK)**: The server immediately sends an `Initial[ACK]` back to the client. The client gets an uninflated RTT sample, reducing PTO and accelerating loss recovery.
    * **The Catch**: If $\Delta t > 3 \times \text{RTT}$, client PTO expires prematurely, causing **spurious probe retransmissions**. Under heavy server load, this triggers cascading probe storms.

    ---

    ### 3. Our Contribution: Load-Aware Instant ACK
    We introduced an adaptive server-side decision engine using a **closed-loop Schmitt-trigger hysteresis controller**:
    $$\text{Decision}(t) = \begin{cases} 
    \text{IACK}, & \text{if } H_{\text{active}}(t) \le \tau_{\text{low}} \\
    \text{WFC}, & \text{if } H_{\text{active}}(t) \ge \tau_{\text{high}} \\
    \text{Decision}(t-1), & \text{otherwise (hysteresis deadband)}
    \end{cases}$$

    * **$\tau_{\text{low}} = 4$**: Safe headroom available $\rightarrow$ deploy fast Instant ACK.
    * **$\tau_{\text{high}} = 8$**: Contention detected $\rightarrow$ fallback to coalescing to protect UDP buffers.
    * **Deadband $[4, 8]$**: Prevents limit-cycle mode-flapping during fluctuating traffic spikes.
    """)
