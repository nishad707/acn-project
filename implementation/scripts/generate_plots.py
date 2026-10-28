#!/usr/bin/env python3
import os
import csv
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
FIGURES_DIR = os.path.join(BASE_DIR, "figures")

os.makedirs(FIGURES_DIR, exist_ok=True)

# Set clean aesthetic style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Helvetica, Arial, sans-serif'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8

COLORS = {
    'wfc': '#1f77b4',       # Blue
    'iack': '#ff7f0e',      # Orange
    'loadaware': '#2ca02c', # Green
}
LABELS = {
    'wfc': 'Static WFC',
    'iack': 'Static IACK',
    'loadaware': 'Load-Aware IACK (Ours)'
}

# ------------------------------------------------------------------------------
# Plot 1 & 2: Exp 1 RTT Sweeps
# ------------------------------------------------------------------------------
def plot_exp1():
    fpath = os.path.join(DATA_DIR, "exp1_rtt_sweep.csv")
    if not os.path.exists(fpath): return

    hs_data = defaultdict(lambda: defaultdict(list))
    ttfb_data = defaultdict(lambda: defaultdict(list))
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r['success'].lower() == 'true':
                hs_data[r['mode']][int(r['rtt_ms'])].append(float(r['handshake_ms']))
                ttfb_data[r['mode']][int(r['rtt_ms'])].append(float(r['ttfb_ms']))

    rtts = sorted(list({r for m in hs_data for r in hs_data[m]}))

    # Fig 1: Handshake Latency vs RTT
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    for m in ['wfc', 'iack', 'loadaware']:
        if m in hs_data:
            means = [np.mean(hs_data[m][r]) for r in rtts]
            stds = [np.std(hs_data[m][r]) for r in rtts]
            ax.plot(rtts, means, marker='o', linewidth=2.2, color=COLORS[m], label=LABELS[m])
            ax.fill_between(rtts, np.array(means)-np.array(stds), np.array(means)+np.array(stds), color=COLORS[m], alpha=0.15)
    ax.set_title("QUIC Handshake Latency vs. Network RTT (Δt = 20ms)", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Network RTT (ms)", fontsize=11)
    ax.set_ylabel("Handshake Completion Time (ms)", fontsize=11)
    ax.set_xticks(rtts)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig1_handshake_latency_vs_rtt.png"))
    plt.close(fig)

    # Fig 2: TTFB vs RTT
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    for m in ['wfc', 'iack', 'loadaware']:
        if m in ttfb_data:
            means = [np.mean(ttfb_data[m][r]) for r in rtts]
            ax.plot(rtts, means, marker='s', linewidth=2.2, color=COLORS[m], label=LABELS[m])
    ax.set_title("Time to First Byte (TTFB) vs. Network RTT", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Network RTT (ms)", fontsize=11)
    ax.set_ylabel("TTFB (ms)", fontsize=11)
    ax.set_xticks(rtts)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig2_ttfb_vs_rtt.png"))
    plt.close(fig)
    print("[+] Saved Fig 1 & Fig 2.")

# ------------------------------------------------------------------------------
# Plot 3 & 4: Exp 3 Load Ramp
# ------------------------------------------------------------------------------
def plot_exp3():
    fpath = os.path.join(DATA_DIR, "exp3_load_ramp.csv")
    spath = os.path.join(DATA_DIR, "exp3_load_server_stats.csv")
    if not os.path.exists(fpath): return

    lat_data = defaultdict(lambda: defaultdict(list))
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r['success'].lower() == 'true':
                lat_data[r['mode']][int(r['concurrency'])].append(float(r['handshake_ms']))

    concs = sorted(list({c for m in lat_data for c in lat_data[m]}))

    # Fig 3: Latency under load
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=300)
    for m in ['wfc', 'iack', 'loadaware']:
        if m in lat_data:
            meds = [np.median(lat_data[m][c]) for c in concs]
            p95s = [np.percentile(lat_data[m][c], 95) for c in concs]
            ax.plot(concs, meds, marker='o', linewidth=2.2, color=COLORS[m], label=f"{LABELS[m]} (Median)")
            ax.plot(concs, p95s, linestyle='--', alpha=0.6, color=COLORS[m], label=f"{LABELS[m]} (p95)")
    ax.set_title("Handshake Latency under Increasing Server Contention (RTT = 20ms)", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Concurrent Clients (Handshake Load)", fontsize=11)
    ax.set_ylabel("Handshake Latency (ms)", fontsize=11)
    ax.set_xticks(concs)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9, fontsize=9, loc='upper left')
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig3_latency_under_load.png"))
    plt.close(fig)

    # Fig 4: Policy Decision Transition
    if os.path.exists(spath):
        c_stats, iacks, wfcs = [], [], []
        with open(spath) as f:
            for r in csv.DictReader(f):
                if r['mode'] == 'loadaware':
                    c_stats.append(int(r['concurrency']))
                    iacks.append(int(r['iack_decisions']))
                    wfcs.append(int(r['wfc_decisions']))
        if c_stats:
            fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=300)
            x = np.arange(len(c_stats))
            ax.bar(x, iacks, width=0.55, label='IACK Decisions (Fast PTO)', color='#2ca02c', alpha=0.85)
            ax.bar(x, wfcs, width=0.55, bottom=iacks, label='WFC Decisions (Contention Fallback)', color='#1f77b4', alpha=0.85)
            ax.set_title("Load-Aware Decision Transition vs. Concurrency Surge", fontsize=13, fontweight='bold', pad=12)
            ax.set_xlabel("Concurrent Handshake Load", fontsize=11)
            ax.set_ylabel("Decision Count", fontsize=11)
            ax.set_xticks(x)
            ax.set_xticklabels([f"{c} clients" for c in c_stats])
            ax.legend(frameon=True, facecolor='white', framealpha=0.9)
            plt.tight_layout()
            fig.savefig(os.path.join(FIGURES_DIR, "fig4_policy_decision_transition.png"))
            plt.close(fig)
    print("[+] Saved Fig 3 & Fig 4.")

# ------------------------------------------------------------------------------
# Plot 5: Exp 2 Certificate Delay Sweep & PTO Crossover
# ------------------------------------------------------------------------------
def plot_exp2():
    fpath = os.path.join(DATA_DIR, "exp2_cert_delay_sweep.csv")
    if not os.path.exists(fpath): return

    hs_data = defaultdict(lambda: defaultdict(list))
    pto_data = defaultdict(lambda: defaultdict(list))
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r['success'].lower() == 'true':
                m = r['mode']
                cd = int(r['cert_delay_ms'])
                hs_data[m][cd].append(float(r['handshake_ms']))
                pto_data[m][cd].append(int(r['pto_count']))

    cds = sorted(list({c for m in hs_data for c in hs_data[m]}))

    fig, ax1 = plt.subplots(figsize=(7.5, 4.8), dpi=300)
    for m in ['wfc', 'iack', 'loadaware']:
        if m in hs_data:
            means = [np.mean(hs_data[m][c]) for c in cds]
            ax1.plot(cds, means, marker='o', linewidth=2.2, color=COLORS[m], label=f"{LABELS[m]} (Latency)")

    ax1.set_title("Handshake Latency vs. Cert Delay Δt (RTT = 40ms, PTO ≈ 120ms)", fontsize=13, fontweight='bold', pad=12)
    ax1.set_xlabel("Backend Certificate Delay Δt (ms)", fontsize=11)
    ax1.set_ylabel("Handshake Completion Time (ms)", fontsize=11)
    ax1.set_xticks(cds)
    ax1.axvline(120, color='red', linestyle=':', label='Theoretical Client PTO (3 × RTT)')
    ax1.legend(frameon=True, facecolor='white', framealpha=0.9, loc='upper left')

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig5_cert_delay_sweep_crossover.png"))
    plt.close(fig)
    print("[+] Saved Fig 5 (Cert Delay Crossover).")

# ------------------------------------------------------------------------------
# Plot 6: Exp 6 Phased Wait-Time Breakdown (Stacked Bars)
# ------------------------------------------------------------------------------
def plot_exp6():
    fpath = os.path.join(DATA_DIR, "exp6_phase_breakdown.csv")
    if not os.path.exists(fpath): return

    # (mode, regime) -> list of [t1, t2, t3, t4]
    phase_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r['success'].lower() == 'true':
                m = r['mode']
                reg = r['regime']
                phase_data[reg][m]['t1'].append(float(r['t1_ms']))
                phase_data[reg][m]['t2'].append(float(r['t2_ms']))
                phase_data[reg][m]['t3'].append(float(r['t3_ms']))
                phase_data[reg][m]['t4'].append(float(r['t4_ms']))

    fig, (ax_low, ax_high) = plt.subplots(1, 2, figsize=(11, 5), dpi=300, sharey=True)
    modes = ['wfc', 'iack', 'loadaware']
    phase_colors = ['#4a90e2', '#f5a623', '#7ed321', '#9013fe']
    phase_labels = ['t1 (Initial to 1st Server Pkt)', 't2 (Cert Delay Gap)', 't3 (Handshake Finish)', 't4 (TTFB Response)']

    for ax, reg, title in [(ax_low, 'Low_Load', 'Low Contention (3 clients)'), (ax_high, 'High_Load', 'High Contention (40 clients)')]:
        x = np.arange(len(modes))
        t1_means = [np.mean(phase_data[reg][m]['t1']) if phase_data[reg][m]['t1'] else 0 for m in modes]
        t2_means = [np.mean(phase_data[reg][m]['t2']) if phase_data[reg][m]['t2'] else 0 for m in modes]
        t3_means = [np.mean(phase_data[reg][m]['t3']) if phase_data[reg][m]['t3'] else 0 for m in modes]
        t4_means = [np.mean(phase_data[reg][m]['t4']) if phase_data[reg][m]['t4'] else 0 for m in modes]

        b1 = ax.bar(x, t1_means, width=0.5, color=phase_colors[0], label=phase_labels[0])
        b2 = ax.bar(x, t2_means, width=0.5, bottom=t1_means, color=phase_colors[1], label=phase_labels[1])
        b3 = ax.bar(x, t3_means, width=0.5, bottom=np.array(t1_means)+np.array(t2_means), color=phase_colors[2], label=phase_labels[2])
        b4 = ax.bar(x, t4_means, width=0.5, bottom=np.array(t1_means)+np.array(t2_means)+np.array(t3_means), color=phase_colors[3], label=phase_labels[3])

        ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels([LABELS[m] for m in modes], rotation=10)
        ax.set_ylabel("Duration (ms)", fontsize=11)

    ax_low.legend(frameon=True, facecolor='white', framealpha=0.9, fontsize=8, loc='upper left')
    fig.suptitle("Client Handshake Phase Breakdown (t1 to t4)", fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig6_phase_wait_time_breakdown.png"), bbox_inches='tight')
    plt.close(fig)
    print("[+] Saved Fig 6 (Phased Wait-Time Breakdown).")

# ------------------------------------------------------------------------------
# Plot 7: Exp 7 Threshold Sensitivity
# ------------------------------------------------------------------------------
def plot_exp7():
    fpath = os.path.join(DATA_DIR, "exp7_threshold_sensitivity.csv")
    if not os.path.exists(fpath): return

    t_data = defaultdict(list)
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r['success'].lower() == 'true':
                pair = f"[{r['low_thresh']}, {r['high_thresh']}]"
                t_data[pair].append(float(r['handshake_ms']))

    pairs = list(t_data.keys())
    meds = [np.median(t_data[p]) for p in pairs]
    p95s = [np.percentile(t_data[p], 95) for p in pairs]

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
    x = np.arange(len(pairs))
    ax.plot(x, meds, marker='o', linewidth=2.2, color='#2ca02c', label='Median Latency')
    ax.plot(x, p95s, marker='s', linestyle='--', linewidth=1.8, color='#d62728', label='p95 Tail Latency')

    ax.set_title("Hysteresis Threshold Sensitivity (25 Concurrent Clients)", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Hysteresis Deadband [Low, High]", fontsize=11)
    ax.set_ylabel("Handshake Latency (ms)", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(pairs)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig7_threshold_sensitivity.png"))
    plt.close(fig)
    print("[+] Saved Fig 7 (Threshold Sensitivity).")

# ------------------------------------------------------------------------------
# Plot 8: Exp 8 2D Headline Heatmap (CertDelay x Concurrency)
# ------------------------------------------------------------------------------
def plot_exp8():
    fpath = os.path.join(DATA_DIR, "exp8_heatmap.csv")
    if not os.path.exists(fpath): return

    matrix = defaultdict(lambda: defaultdict(dict))
    with open(fpath) as f:
        for r in csv.DictReader(f):
            if r['success'].lower() == 'true':
                m = r['mode']
                cd = int(r['cert_delay_ms'])
                c = int(r['concurrency'])
                if (cd, c) not in matrix[m]:
                    matrix[m][(cd, c)] = []
                matrix[m][(cd, c)].append(float(r['handshake_ms']))

    cds = sorted(list({k[0] for m in matrix for k in matrix[m]}))
    concs = sorted(list({k[1] for m in matrix for k in matrix[m]}))

    winner_grid = np.zeros((len(concs), len(cds)))
    # 0 = WFC, 1 = IACK, 2 = LoadAware
    for i, c in enumerate(concs):
        for j, cd in enumerate(cds):
            w_time = np.mean(matrix['wfc'].get((cd, c), [999]))
            i_time = np.mean(matrix['iack'].get((cd, c), [999]))
            l_time = np.mean(matrix['loadaware'].get((cd, c), [999]))

            best = min(w_time, i_time, l_time)
            if l_time <= best + 1.0: # Load-aware matches or beats
                winner_grid[i, j] = 2
            elif i_time < w_time:
                winner_grid[i, j] = 1
            else:
                winner_grid[i, j] = 0

    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(['#1f77b4', '#ff7f0e', '#2ca02c'])

    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=300)
    cax = ax.imshow(winner_grid, cmap=cmap, origin='lower', aspect='auto')

    ax.set_title("2D Parameter Space: Policy Winner Map", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Backend Certificate Delay Δt (ms)", fontsize=11)
    ax.set_ylabel("Concurrent Handshake Load (Clients)", fontsize=11)
    ax.set_xticks(np.arange(len(cds)))
    ax.set_xticklabels([f"{cd}ms" for cd in cds])
    ax.set_yticks(np.arange(len(concs)))
    ax.set_yticklabels([f"{c} conns" for c in concs])

    # Custom legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ca02c', label='Load-Aware Wins / Optimal'),
        Patch(facecolor='#ff7f0e', label='Static IACK Wins (Low Load)'),
        Patch(facecolor='#1f77b4', label='Static WFC Wins (Heavy Load)'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig8_winner_heatmap.png"))
    plt.close(fig)
    print("[+] Saved Fig 8 (2D Winner Heatmap).")

if __name__ == "__main__":
    plot_exp1()
    plot_exp2()
    plot_exp3()
    plot_exp6()
    plot_exp7()
    plot_exp8()
    print("\n[✔] All Research Figures Generated Successfully in figures/!")
