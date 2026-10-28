import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

FIGURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "figures"))
os.makedirs(FIGURES_DIR, exist_ok=True)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans, Arial, sans-serif'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8

# ==============================================================================
# DIAGRAM 1: CDN Edge-Backend Split Architecture
# ==============================================================================
def make_cdn_diagram():
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis('off')

    # Background zones
    rect_client = patches.FancyBboxPatch((0.5, 0.8), 2.0, 3.4, boxstyle="round,pad=0.2", facecolor="#e8f4fd", edgecolor="#2980b9", lw=2)
    rect_edge = patches.FancyBboxPatch((3.8, 0.8), 2.5, 3.4, boxstyle="round,pad=0.2", facecolor="#eafaf1", edgecolor="#27ae60", lw=2)
    rect_backend = patches.FancyBboxPatch((7.5, 0.8), 2.0, 3.4, boxstyle="round,pad=0.2", facecolor="#fef5e7", edgecolor="#e67e22", lw=2)

    ax.add_patch(rect_client)
    ax.add_patch(rect_edge)
    ax.add_patch(rect_backend)

    # Zone Titles
    ax.text(1.5, 3.8, "Client Device", ha="center", va="center", fontsize=13, fontweight="bold", color="#1f618d")
    ax.text(1.5, 3.4, "Browser / App\n(RFC 9002 QUIC)", ha="center", va="center", fontsize=9, color="#555")

    ax.text(5.05, 3.8, "CDN Edge PoP", ha="center", va="center", fontsize=13, fontweight="bold", color="#1e8449")
    ax.text(5.05, 3.4, "Frontend QUIC Proxy\n(e.g., Cloudflare, Akamai)", ha="center", va="center", fontsize=9, color="#555")

    ax.text(8.5, 3.8, "Backend Store", ha="center", va="center", fontsize=13, fontweight="bold", color="#d35400")
    ax.text(8.5, 3.4, "Central Keyless SSL\nPrivate Key / Cert Store", ha="center", va="center", fontsize=9, color="#555")

    # Arrows and Latencies
    # Client <-> Edge
    ax.annotate("", xy=(3.6, 2.5), xytext=(2.7, 2.5),
                arrowprops=dict(arrowstyle="<->", lw=2.5, color="#2980b9"))
    ax.text(3.15, 2.8, "Network RTT\n(10 - 100 ms)", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#2980b9")

    # Edge <-> Backend
    ax.annotate("", xy=(7.3, 2.5), xytext=(6.5, 2.5),
                arrowprops=dict(arrowstyle="<->", lw=2.5, color="#e67e22"))
    ax.text(6.9, 2.8, "Backend Delay Δt\n(2 - 200 ms)", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#e67e22")

    # Sub-boxes inside Edge
    box_iack = patches.FancyBboxPatch((4.0, 1.9), 2.1, 0.7, boxstyle="round,pad=0.1", facecolor="#27ae60", edgecolor="none")
    ax.add_patch(box_iack)
    ax.text(5.05, 2.25, "Option A: Instant ACK\nSend Initial[ACK] immediately", ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")

    box_wfc = patches.FancyBboxPatch((4.0, 1.0), 2.1, 0.7, boxstyle="round,pad=0.1", facecolor="#2980b9", edgecolor="none")
    ax.add_patch(box_wfc)
    ax.text(5.05, 1.35, "Option B: Wait-for-Cert\nHold back until cert arrives", ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")

    # Key Dilemma text at bottom
    ax.text(5.0, 0.3, "The CDN Dilemma: Respond immediately (2 UDP flights) or wait for backend (1 coalesced flight)?",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#2c3e50")

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "diag_cdn_architecture.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Generated diag_cdn_architecture.png")

# ==============================================================================
# DIAGRAM 2: Handshake Sequence Flow (WFC vs IACK vs Spurious Failure)
# ==============================================================================
def make_handshake_flow():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(13, 5.5), dpi=300)
    for ax in [ax1, ax2, ax3]:
        ax.set_xlim(0, 4)
        ax.set_ylim(0, 10)
        ax.axis('off')

    def draw_timelines(ax, title, color):
        ax.text(2, 9.6, title, ha="center", va="center", fontsize=11, fontweight="bold", color=color)
        ax.plot([1, 1], [1, 9], color="#7f8c8d", lw=2) # Client line
        ax.plot([3, 3], [1, 9], color="#7f8c8d", lw=2) # Server line
        ax.text(1, 9.1, "Client", ha="center", fontsize=10, fontweight="bold")
        ax.text(3, 9.1, "Server", ha="center", fontsize=10, fontweight="bold")

    # --- Mode 1: Static WFC ---
    draw_timelines(ax1, "1. Static Wait-for-Cert (WFC)", "#1f77b4")
    # ClientHello
    ax1.annotate("", xy=(3, 7.8), xytext=(1, 8.5), arrowprops=dict(arrowstyle="->", lw=1.8, color="#2c3e50"))
    ax1.text(2, 8.35, "ClientHello", ha="center", fontsize=8.5, rotation=-19)
    # Server waiting
    rect_wait = patches.Rectangle((2.9, 5.8), 0.2, 2.0, facecolor="#f39c12", edgecolor="none")
    ax1.add_patch(rect_wait)
    ax1.text(3.4, 6.8, "Wait Δt\n(Cert fetch)", va="center", fontsize=8, color="#d35400")
    # Coalesced Response
    ax1.annotate("", xy=(1, 5.0), xytext=(3, 5.8), arrowprops=dict(arrowstyle="->", lw=2.2, color="#1f77b4"))
    ax1.text(2, 5.65, "Initial[ACK, Crypto] +\nHandshake[Cert, Fin]", ha="center", fontsize=8, color="#1f77b4", rotation=22)
    # RTT measurement & PTO
    ax1.plot([0.8, 0.8], [5.0, 8.5], color="#e74c3c", lw=1.5, linestyle="--")
    ax1.text(0.7, 6.75, "Measured RTT =\nRTT + Δt\n(INFLATED)", ha="right", va="center", fontsize=8, color="#c0392b", fontweight="bold")
    ax1.text(2, 2.0, "• 1 Single Flight (Coalesced)\n• Initial PTO is INFLATED:\n  PTO ≈ 3 × (RTT + Δt)\n• Loss recovery delayed by 3Δt",
             ha="center", fontsize=8.5, bbox=dict(boxstyle="round,pad=0.4", facecolor="#eaf2f8", edgecolor="#aed6f1"))

    # --- Mode 2: Static Instant ACK (IACK) ---
    draw_timelines(ax2, "2. Static Instant ACK (IACK)", "#ff7f0e")
    # ClientHello
    ax2.annotate("", xy=(3, 7.8), xytext=(1, 8.5), arrowprops=dict(arrowstyle="->", lw=1.8, color="#2c3e50"))
    ax2.text(2, 8.35, "ClientHello", ha="center", fontsize=8.5, rotation=-19)
    # Instant ACK
    ax2.annotate("", xy=(1, 7.1), xytext=(3, 7.8), arrowprops=dict(arrowstyle="->", lw=2.0, color="#27ae60"))
    ax2.text(2, 7.65, "Initial[ACK] (Flight 1)", ha="center", fontsize=8.5, color="#27ae60", rotation=19)
    # True RTT
    ax2.plot([0.8, 0.8], [7.1, 8.5], color="#27ae60", lw=1.5, linestyle="--")
    ax2.text(0.7, 7.8, "True RTT\n(ACCURATE)", ha="right", va="center", fontsize=8, color="#27ae60", fontweight="bold")
    # Cert delay wait
    rect_wait2 = patches.Rectangle((2.9, 5.5), 0.2, 2.3, facecolor="#f39c12", edgecolor="none")
    ax2.add_patch(rect_wait2)
    ax2.text(3.4, 6.6, "Wait Δt", va="center", fontsize=8, color="#d35400")
    # Second Flight
    ax2.annotate("", xy=(1, 4.8), xytext=(3, 5.5), arrowprops=dict(arrowstyle="->", lw=1.8, color="#ff7f0e"))
    ax2.text(2, 5.35, "Handshake[Cert, Fin] (Flight 2)", ha="center", fontsize=8, color="#d35400", rotation=19)
    ax2.text(2, 2.0, "• 2 UDP Flights (Split)\n• Accurate initial PTO:\n  PTO ≈ 3 × RTT\n• Loss recovery 15-20ms faster\n• 2x sendmsg syscalls",
             ha="center", fontsize=8.5, bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef5e7", edgecolor="#f8c471"))

    # --- Mode 3: IACK Failure Under Load ---
    draw_timelines(ax3, "3. Contention Breakdown (Failure)", "#c0392b")
    # ClientHello
    ax3.annotate("", xy=(3, 7.8), xytext=(1, 8.5), arrowprops=dict(arrowstyle="->", lw=1.8, color="#2c3e50"))
    # Instant ACK
    ax3.annotate("", xy=(1, 7.1), xytext=(3, 7.8), arrowprops=dict(arrowstyle="->", lw=2.0, color="#27ae60"))
    ax3.text(2, 7.65, "Initial[ACK]", ha="center", fontsize=8.5, color="#27ae60", rotation=19)
    # Long Queued Cert Delay
    rect_wait3 = patches.Rectangle((2.9, 3.8), 0.2, 4.0, facecolor="#e74c3c", edgecolor="none")
    ax3.add_patch(rect_wait3)
    ax3.text(3.4, 5.8, "Severe Queueing\nΔt_eff > 3×RTT", va="center", fontsize=8, color="#c0392b", fontweight="bold")
    # Client PTO Fires!
    ax3.plot([1, 1], [5.6, 7.1], color="#c0392b", lw=2.5, linestyle=":")
    ax3.text(0.7, 5.6, "PTO Timer\nExpires!", ha="right", va="center", fontsize=8, color="#c0392b", fontweight="bold")
    ax3.annotate("", xy=(3, 4.9), xytext=(1, 5.6), arrowprops=dict(arrowstyle="->", lw=2.0, color="#c0392b", linestyle="dashed"))
    ax3.text(2, 5.4, "Spurious PTO Probe!", ha="center", fontsize=8, color="#c0392b", fontweight="bold", rotation=-19)
    # Late Cert
    ax3.annotate("", xy=(1, 3.1), xytext=(3, 3.8), arrowprops=dict(arrowstyle="->", lw=1.5, color="#7f8c8d"))
    ax3.text(2, 3.65, "Late Cert (Redundant)", ha="center", fontsize=7.5, color="#7f8c8d", rotation=19)
    ax3.text(2, 1.5, "FAILURE CONDITION:\nΔt_effective > 3 × RTT\nTriggers Thundering Herd\nof Spurious PTO Probes!",
             ha="center", fontsize=8.5, color="#c0392b", fontweight="bold", bbox=dict(boxstyle="round,pad=0.4", facecolor="#fadbd8", edgecolor="#e74c3c"))

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "diag_handshake_flow.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Generated diag_handshake_flow.png")

# ==============================================================================
# DIAGRAM 3: Schmitt-Trigger Hysteresis State Machine
# ==============================================================================
def make_hysteresis_diagram():
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis('off')

    # State IACK Box
    box_iack = patches.FancyBboxPatch((0.8, 1.8), 2.4, 2.0, boxstyle="round,pad=0.2", facecolor="#eafaf1", edgecolor="#27ae60", lw=2.5)
    ax.add_patch(box_iack)
    ax.text(2.0, 3.2, "STATE: IACK", ha="center", va="center", fontsize=13, fontweight="bold", color="#1e8449")
    ax.text(2.0, 2.6, "• Emit Initial[ACK] fast\n• True RTT calibration\n• Tight PTO (3×RTT)\n• Best for light load",
            ha="center", va="center", fontsize=8.5, color="#333")

    # State WFC Box
    box_wfc = patches.FancyBboxPatch((6.8, 1.8), 2.4, 2.0, boxstyle="round,pad=0.2", facecolor="#ebf5fb", edgecolor="#2980b9", lw=2.5)
    ax.add_patch(box_wfc)
    ax.text(8.0, 3.2, "STATE: WFC", ha="center", va="center", fontsize=13, fontweight="bold", color="#1f618d")
    ax.text(8.0, 2.6, "• Coalesce into 1 packet\n• Halve sendmsg syscalls\n• Protect socket buffer\n• Suppress probe storms",
            ha="center", va="center", fontsize=8.5, color="#333")

    # Deadband Center Box
    box_dead = patches.FancyBboxPatch((3.8, 2.1), 2.4, 1.4, boxstyle="round,pad=0.2", facecolor="#fef9e7", edgecolor="#f1c40f", lw=2, linestyle="--")
    ax.add_patch(box_dead)
    ax.text(5.0, 3.0, "HYSTERESIS DEADBAND", ha="center", va="center", fontsize=10, fontweight="bold", color="#b7950b")
    ax.text(5.0, 2.5, "4 < Active Conns < 8\nRetain Previous State\n(Zero Mode-Flapping)", ha="center", va="center", fontsize=8, color="#555")

    # Transition Arrows
    # Transition to WFC (Top)
    ax.annotate("", xy=(6.6, 3.4), xytext=(3.4, 3.4),
                arrowprops=dict(arrowstyle="->", lw=2.5, color="#c0392b"))
    ax.text(5.0, 3.75, "Active Conns >= 8 (τ_high)\nSwitch to Coalesced WFC", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#c0392b")

    # Transition to IACK (Bottom)
    ax.annotate("", xy=(3.4, 1.2), xytext=(6.6, 1.2),
                arrowprops=dict(arrowstyle="->", lw=2.5, color="#27ae60"))
    ax.text(5.0, 0.75, "Active Conns <= 4 (τ_low)\nSwitch to Instant ACK", ha="center", va="top", fontsize=9, fontweight="bold", color="#27ae60")

    ax.text(5.0, 4.6, "Schmitt-Trigger Closed-Loop Hysteresis Engine", ha="center", va="center", fontsize=14, fontweight="bold", color="#2c3e50")

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "diag_hysteresis_state_machine.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Generated diag_hysteresis_state_machine.png")

# ==============================================================================
# DIAGRAM 4: System Implementation Architecture Block Diagram
# ==============================================================================
def make_system_architecture():
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis('off')

    # Component 1: Client
    p_client = patches.FancyBboxPatch((0.5, 1.2), 2.2, 3.0, boxstyle="round,pad=0.2", facecolor="#f4ecf7", edgecolor="#8e44ad", lw=2)
    ax.add_patch(p_client)
    ax.text(1.6, 3.8, "Measurement Client", ha="center", va="center", fontsize=11, fontweight="bold", color="#6c3483")
    ax.text(1.6, 3.4, "cmd/client/main.go", ha="center", va="center", fontsize=8.5, color="#7d3c98", style="italic")
    ax.text(1.6, 2.4, "• Multi-worker goroutines\n• Nanosecond timers (t1-t4)\n• TTFB measurement\n• Intercepts UpdatedPTOCount\n  without breaking TLS",
            ha="center", va="center", fontsize=8, color="#333")

    # Component 2: UDP Proxy Network Emulator
    p_proxy = patches.FancyBboxPatch((3.8, 1.2), 2.4, 3.0, boxstyle="round,pad=0.2", facecolor="#fef9e7", edgecolor="#f39c12", lw=2)
    ax.add_patch(p_proxy)
    ax.text(5.0, 3.8, "UDP Network Proxy", ha="center", va="center", fontsize=11, fontweight="bold", color="#b9770e")
    ax.text(5.0, 3.4, "cmd/proxy/main.go", ha="center", va="center", fontsize=8.5, color="#935116", style="italic")
    ax.text(5.0, 2.4, "• Bidirectional delay (RTT/2)\n• 4MB UDP socket buffers\n  (SetReadBuffer)\n• Packet loss injection (0-8%)\n• Delay jitter (±45ms)",
            ha="center", va="center", fontsize=8, color="#333")

    # Component 3: QUIC Server with LoadMonitor
    p_server = patches.FancyBboxPatch((7.3, 1.2), 2.2, 3.0, boxstyle="round,pad=0.2", facecolor="#e8f8f5", edgecolor="#16a085", lw=2)
    ax.add_patch(p_server)
    ax.text(8.4, 3.8, "Multi-Mode QUIC Server", ha="center", va="center", fontsize=11, fontweight="bold", color="#117864")
    ax.text(8.4, 3.4, "cmd/server/main.go", ha="center", va="center", fontsize=8.5, color="#0e6252", style="italic")
    ax.text(8.4, 2.4, "• quic-go + qtls-go1-20\n• connection.go hooks\n• loadmonitor.go [4, 8]\n• Simulated cert delay Δt\n• JSON Metrics at :8080/stats",
            ha="center", va="center", fontsize=8, color="#333")

    # Traffic Flow Arrows
    ax.annotate("", xy=(3.6, 2.8), xytext=(2.9, 2.8), arrowprops=dict(arrowstyle="<->", lw=2.2, color="#2c3e50"))
    ax.text(3.25, 3.0, "UDP Loopback", ha="center", fontsize=8, fontweight="bold")

    ax.annotate("", xy=(7.1, 2.8), xytext=(6.4, 2.8), arrowprops=dict(arrowstyle="<->", lw=2.2, color="#2c3e50"))
    ax.text(6.75, 3.0, "Emulated Path", ha="center", fontsize=8, fontweight="bold")

    # Streamlit dashboard connection
    p_dash = patches.FancyBboxPatch((6.0, 0.1), 3.5, 0.7, boxstyle="round,pad=0.1", facecolor="#eaf2f8", edgecolor="#2980b9", lw=1.5)
    ax.add_patch(p_dash)
    ax.text(7.75, 0.45, "Real-Time Streamlit Dashboard (:8501)", ha="center", va="center", fontsize=9, fontweight="bold", color="#1f618d")
    ax.annotate("", xy=(8.0, 1.0), xytext=(8.0, 0.9), arrowprops=dict(arrowstyle="->", lw=1.8, color="#2980b9"))

    ax.text(5.0, 4.65, "End-to-End Experimental Testbed Architecture", ha="center", va="center", fontsize=14, fontweight="bold", color="#2c3e50")

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "diag_system_architecture.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Generated diag_system_architecture.png")

# ==============================================================================
# DIAGRAM 5: Stress Test Findings Visual Comparison
# ==============================================================================
def make_stress_comparison():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8), dpi=300)

    # Subplot 1: Flash Crowd & Surge Latencies (ms)
    scenarios = ['Exp B: 200 Flash\n(Sweet Spot)', 'Exp B: 250 Flash\n(Heavy Surge)', 'Exp A.3: 500 Burst\n(Massive Wave)', 'Exp C: 5% Loss\n(p95 Tail)']
    wfc_vals = [920.9, 950.5, 1149.7, 328.6]
    iack_vals = [759.4, 726.3, 1925.3, 131.2]
    la_vals = [337.7, 502.3, 752.5, 129.9]

    x = np.arange(len(scenarios))
    w = 0.25

    ax1.bar(x - w, wfc_vals, width=w, label='Static WFC', color='#1f77b4', alpha=0.85)
    ax1.bar(x, iack_vals, width=w, label='Static IACK', color='#ff7f0e', alpha=0.85)
    ax1.bar(x + w, la_vals, width=w, label='Load-Aware (Ours)', color='#2ca02c', alpha=0.95)

    ax1.set_title("Stress Benchmark Latency Comparison", fontsize=11, fontweight='bold', pad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontsize=8)
    ax1.set_ylabel("Latency (ms)", fontsize=10)
    ax1.legend(frameon=True, facecolor='white', fontsize=8.5)

    # Subplot 2: PTO Probes Fired under Heavy Stress
    pto_scenarios = ['Exp B: 200 Flash', 'Exp A.3: 500 Burst', 'Exp D: Pulsing Surge', 'Exp E: Delay Jitter']
    wfc_ptos = [331, 1061, 38, 0]
    iack_ptos = [271, 1057, 50, 2]
    la_ptos = [201, 959, 31, 0]

    x2 = np.arange(len(pto_scenarios))
    ax2.bar(x2 - w, wfc_ptos, width=w, label='Static WFC', color='#1f77b4', alpha=0.85)
    ax2.bar(x2, iack_ptos, width=w, label='Static IACK', color='#ff7f0e', alpha=0.85)
    ax2.bar(x2 + w, la_ptos, width=w, label='Load-Aware (Ours)', color='#2ca02c', alpha=0.95)

    ax2.set_title("Spurious PTO Probes Fired (Probe Storms)", fontsize=11, fontweight='bold', pad=10)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(pto_scenarios, fontsize=8)
    ax2.set_ylabel("PTO Probes Fired", fontsize=10)
    ax2.legend(frameon=True, facecolor='white', fontsize=8.5)

    fig.suptitle("Stress Test Discoveries: Load-Aware Dominance & Probe Suppression", fontsize=13, fontweight='bold', y=0.98)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "diag_stress_tests_summary.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Generated diag_stress_tests_summary.png")

# ==============================================================================
# DIAGRAM 6: Load-Aware v1 vs. v2 Head-to-Head Comparison
# ==============================================================================
def make_v1_v2_comparison():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8), dpi=300)

    # Subplot 1: Latency Head-to-Head
    tests = ['Peacetime\n(Exp 1)', '100 Flash\nCrowd', '250 Severe\nSurge', 'Wireless\nJitter (±45ms)']
    v1_lat = [34.2, 299.5, 1064.4, 101.9]
    v2_lat = [34.1, 203.5, 771.1, 88.0]

    x = np.arange(len(tests))
    w = 0.32
    ax1.bar(x - w/2, v1_lat, width=w, label='Load-Aware v1 (Baseline)', color='#3498db', alpha=0.85)
    ax1.bar(x + w/2, v2_lat, width=w, label='Load-Aware v2 (Lock-Free+Velocity)', color='#2ecc71', alpha=0.95)

    for i in range(len(tests)):
        diff = ((v2_lat[i] - v1_lat[i]) / v1_lat[i]) * 100
        if diff < -5:
            ax1.text(x[i] + w/2, v2_lat[i] + 25, f"{diff:.1f}%", ha='center', fontsize=8, fontweight='bold', color='#27ae60')

    ax1.set_title("Latency: Load-Aware v1 vs. v2", fontsize=11, fontweight='bold', pad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(tests, fontsize=8.5)
    ax1.set_ylabel("Handshake Latency (ms)", fontsize=10)
    ax1.legend(frameon=True, facecolor='white', fontsize=8.5)

    # Subplot 2: Architectural Metrics Comparison
    metrics = ['100 Flash PTOs', '5,000 Overload PTOs', 'Decision Latency (ns)']
    v1_m = [88, 4875, 150]
    v2_m = [44, 3112, 5]

    x2 = np.arange(len(metrics))
    b1 = ax2.bar(x2 - w/2, [88, 4875/100, 150], width=w, label='Load-Aware v1', color='#3498db', alpha=0.85)
    b2 = ax2.bar(x2 + w/2, [44, 3112/100, 5], width=w, label='Load-Aware v2', color='#2ecc71', alpha=0.95)

    ax2.set_title("Probe Storms & Fast-Path Latency", fontsize=11, fontweight='bold', pad=10)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(['100 Flash\nPTO Count', '5k Overload\nPTOs (x100)', 'Decision Latency\n(Nanoseconds)'], fontsize=8.5)
    ax2.set_ylabel("Value (Normalized)", fontsize=10)
    ax2.legend(frameon=True, facecolor='white', fontsize=8.5)

    ax2.text(0 + w/2, 48, "-50% PTOs", ha='center', fontsize=8, fontweight='bold', color='#27ae60')
    ax2.text(1 + w/2, 33, "-36.2%", ha='center', fontsize=8, fontweight='bold', color='#27ae60')
    ax2.text(2 + w/2, 8, "30x Faster!", ha='center', fontsize=8, fontweight='bold', color='#27ae60')

    fig.suptitle("Evolution to Load-Aware v2: Lock-Free & Velocity-Aware Gains", fontsize=13, fontweight='bold', y=0.98)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "diag_v1_vs_v2_comparison.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Generated diag_v1_vs_v2_comparison.png")

if __name__ == "__main__":
    make_cdn_diagram()
    make_handshake_flow()
    make_hysteresis_diagram()
    make_system_architecture()
    make_stress_comparison()
    make_v1_v2_comparison()
    print("\n[OK] All Presentation Visual Diagrams Successfully Rendered!")
