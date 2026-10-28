#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import json
import csv
import urllib.request

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BIN_DIR = os.path.join(BASE_DIR, "implementation", "bin")
SERVER_BIN = os.path.join(BIN_DIR, "server")
PROXY_BIN = os.path.join(BIN_DIR, "proxy")
CLIENT_BIN = os.path.join(BIN_DIR, "client")
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

def kill_processes():
    subprocess.run(["pkill", "-f", SERVER_BIN], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", PROXY_BIN], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", CLIENT_BIN], stderr=subprocess.DEVNULL)
    time.sleep(0.4)

def fetch_server_stats(port=8080):
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/stats", timeout=2)
        return json.loads(req.read().decode())
    except Exception:
        return {}

def start_server_and_proxy(mode, cert_delay="20ms", rtt_ms=20, low_thresh=4, high_thresh=8):
    kill_processes()
    server_cmd = [
        SERVER_BIN,
        f"--mode={mode}",
        "--addr=127.0.0.1:4433",
        f"--cert-delay={cert_delay}",
        f"--low-thresh={low_thresh}",
        f"--high-thresh={high_thresh}",
        "--metrics-addr=127.0.0.1:8080"
    ]
    subprocess.Popen(server_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)

    proxy_cmd = [
        PROXY_BIN,
        "--listen=127.0.0.1:6000",
        "--target=127.0.0.1:4433",
        f"--rtt={rtt_ms}ms",
        "--loss=0.0"
    ]
    subprocess.Popen(proxy_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)

# ==============================================================================
# Exp 1: Baseline RTT Sweeps (Light Load)
# ==============================================================================
def run_exp1_rtt_sweep():
    print("\n" + "="*70)
    print(">>> Running Experiment 1: Baseline RTT Sweeps (Light Load)")
    print("="*70)
    modes = ["wfc", "iack", "loadaware"]
    rtts = [10, 30, 60, 100]
    out_file = os.path.join(DATA_DIR, "exp1_rtt_sweep.csv")

    with open(out_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "rtt_ms", "rep", "handshake_ms", "ttfb_ms", "total_ms", "t1_ms", "t2_ms", "t3_ms", "t4_ms", "pto_count", "success"])
        for mode in modes:
            for rtt in rtts:
                print(f"[*] Mode={mode:<10} | RTT={rtt:>3}ms ...", end="", flush=True)
                start_server_and_proxy(mode=mode, cert_delay="20ms", rtt_ms=rtt)
                for rep in range(5):
                    cmd = [CLIENT_BIN, "--target=127.0.0.1:6000", "--concurrency=1", "--requests=1", "--csv"]
                    out = subprocess.check_output(cmd).decode()
                    for line in out.splitlines()[1:]:
                        parts = line.strip().split(",")
                        if len(parts) >= 11:
                            w.writerow([mode, rtt, rep, parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7], parts[8], parts[10]])
                kill_processes()
                print(" Done.")
    print(f"[+] Saved to: {out_file}")

# ==============================================================================
# Exp 2: Certificate Delay Sweep (Finding PTO Crossover Point)
# ==============================================================================
def run_exp2_cert_delay_sweep():
    print("\n" + "="*70)
    print(">>> Running Experiment 2: Certificate Delay Sweep (Δt Crossover)")
    print("="*70)
    modes = ["wfc", "iack", "loadaware"]
    cert_delays = [10, 25, 50, 100, 180] # ms
    rtt = 40 # ms (client PTO initial is ~120ms)
    out_file = os.path.join(DATA_DIR, "exp2_cert_delay_sweep.csv")

    with open(out_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "cert_delay_ms", "rep", "handshake_ms", "ttfb_ms", "t1_ms", "t2_ms", "pto_count", "success"])
        for mode in modes:
            for cd in cert_delays:
                print(f"[*] Mode={mode:<10} | CertDelay={cd:>3}ms | RTT={rtt}ms ...", end="", flush=True)
                start_server_and_proxy(mode=mode, cert_delay=f"{cd}ms", rtt_ms=rtt)
                for rep in range(4):
                    cmd = [CLIENT_BIN, "--target=127.0.0.1:6000", "--concurrency=1", "--requests=1", "--csv"]
                    out = subprocess.check_output(cmd).decode()
                    for line in out.splitlines()[1:]:
                        parts = line.strip().split(",")
                        if len(parts) >= 11:
                            w.writerow([mode, cd, rep, parts[1], parts[2], parts[4], parts[5], parts[8], parts[10]])
                kill_processes()
                print(" Done.")
    print(f"[+] Saved to: {out_file}")

# ==============================================================================
# Exp 3: Concurrency & Load Ramp (The Core Thesis!)
# ==============================================================================
def run_exp3_load_ramp():
    print("\n" + "="*70)
    print(">>> Running Experiment 3: Server Load Ramp (Concurrency 1 - 75)")
    print("="*70)
    modes = ["wfc", "iack", "loadaware"]
    concurrency_levels = [1, 5, 10, 20, 35, 50, 75]
    out_file = os.path.join(DATA_DIR, "exp3_load_ramp.csv")
    stats_file = os.path.join(DATA_DIR, "exp3_load_server_stats.csv")

    with open(out_file, "w", newline="") as rf, open(stats_file, "w", newline="") as sf:
        rw = csv.writer(rf)
        rw.writerow(["mode", "concurrency", "worker_id", "handshake_ms", "ttfb_ms", "total_ms", "pto_count", "success"])
        sw = csv.writer(sf)
        sw.writerow(["mode", "concurrency", "active_peak", "total_started", "total_completed", "iack_decisions", "wfc_decisions", "final_mode"])

        for mode in modes:
            for conc in concurrency_levels:
                print(f"[*] Mode={mode:<10} | Concurrency={conc:>2} clients ...", end="", flush=True)
                start_server_and_proxy(mode=mode, cert_delay="20ms", rtt_ms=20, low_thresh=4, high_thresh=8)

                cmd = [CLIENT_BIN, "--target=127.0.0.1:6000", f"--concurrency={conc}", "--requests=2", "--csv"]
                out = subprocess.check_output(cmd).decode()
                for line in out.splitlines()[1:]:
                    parts = line.strip().split(",")
                    if len(parts) >= 11:
                        rw.writerow([mode, conc, parts[0], parts[1], parts[2], parts[3], parts[8], parts[10]])

                time.sleep(0.4)
                stats = fetch_server_stats()
                sw.writerow([
                    mode,
                    conc,
                    stats.get("peak_handshakes", 0),
                    stats.get("total_started", 0),
                    stats.get("total_completed", 0),
                    stats.get("iack_decisions", 0),
                    stats.get("wfc_decisions", 0),
                    stats.get("current_state", "N/A")
                ])
                kill_processes()
                print(" Done.")
    print(f"[+] Saved to: {out_file} & {stats_file}")

# ==============================================================================
# Exp 6: Phased Wait-Time Breakdown (t1, t2, t3, t4)
# ==============================================================================
def run_exp6_phase_breakdown():
    print("\n" + "="*70)
    print(">>> Running Experiment 6: Phased Client Wait-Time Breakdown")
    print("="*70)
    modes = ["wfc", "iack", "loadaware"]
    regimes = [("Low_Load", 3), ("High_Load", 40)]
    out_file = os.path.join(DATA_DIR, "exp6_phase_breakdown.csv")

    with open(out_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "regime", "worker_id", "handshake_ms", "t1_ms", "t2_ms", "t3_ms", "t4_ms", "success"])
        for mode in modes:
            for reg_name, conc in regimes:
                print(f"[*] Mode={mode:<10} | Regime={reg_name} ({conc} clients) ...", end="", flush=True)
                start_server_and_proxy(mode=mode, cert_delay="25ms", rtt_ms=30)
                cmd = [CLIENT_BIN, "--target=127.0.0.1:6000", f"--concurrency={conc}", "--requests=2", "--csv"]
                out = subprocess.check_output(cmd).decode()
                for line in out.splitlines()[1:]:
                    parts = line.strip().split(",")
                    if len(parts) >= 11:
                        w.writerow([mode, reg_name, parts[0], parts[1], parts[4], parts[5], parts[6], parts[7], parts[10]])
                kill_processes()
                print(" Done.")
    print(f"[+] Saved to: {out_file}")

# ==============================================================================
# Exp 7: Threshold Sensitivity Analysis
# ==============================================================================
def run_exp7_threshold_sensitivity():
    print("\n" + "="*70)
    print(">>> Running Experiment 7: Threshold Sensitivity Analysis")
    print("="*70)
    thresholds = [(2, 4), (4, 8), (8, 16), (15, 30)]
    concurrency = 25
    out_file = os.path.join(DATA_DIR, "exp7_threshold_sensitivity.csv")

    with open(out_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["low_thresh", "high_thresh", "worker_id", "handshake_ms", "ttfb_ms", "success"])
        for lt, ht in thresholds:
            print(f"[*] Testing Thresholds=[low={lt}, high={ht}] at Concurrency={concurrency} ...", end="", flush=True)
            start_server_and_proxy(mode="loadaware", cert_delay="20ms", rtt_ms=20, low_thresh=lt, high_thresh=ht)
            cmd = [CLIENT_BIN, "--target=127.0.0.1:6000", f"--concurrency={concurrency}", "--requests=2", "--csv"]
            out = subprocess.check_output(cmd).decode()
            for line in out.splitlines()[1:]:
                parts = line.strip().split(",")
                if len(parts) >= 11:
                    w.writerow([lt, ht, parts[0], parts[1], parts[2], parts[10]])
            kill_processes()
            print(" Done.")
    print(f"[+] Saved to: {out_file}")

# ==============================================================================
# Exp 8: 2D Headline Heatmap Matrix (CertDelay x Concurrency)
# ==============================================================================
def run_exp8_heatmap():
    print("\n" + "="*70)
    print(">>> Running Experiment 8: 2D Headline Parameter Heatmap")
    print("="*70)
    modes = ["wfc", "iack", "loadaware"]
    cert_delays = [10, 30, 60, 100]
    concurrencies = [1, 10, 25, 50]
    out_file = os.path.join(DATA_DIR, "exp8_heatmap.csv")

    with open(out_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "cert_delay_ms", "concurrency", "worker_id", "handshake_ms", "success"])
        for cd in cert_delays:
            for conc in concurrencies:
                for mode in modes:
                    print(f"[*] CD={cd:>3}ms | Conc={conc:>2} | Mode={mode:<9} ...", end="", flush=True)
                    start_server_and_proxy(mode=mode, cert_delay=f"{cd}ms", rtt_ms=20)
                    cmd = [CLIENT_BIN, "--target=127.0.0.1:6000", f"--concurrency={conc}", "--requests=1", "--csv"]
                    out = subprocess.check_output(cmd).decode()
                    for line in out.splitlines()[1:]:
                        parts = line.strip().split(",")
                        if len(parts) >= 11:
                            w.writerow([mode, cd, conc, parts[0], parts[1], parts[10]])
                    kill_processes()
                    print(" Done.")
    print(f"[+] Saved to: {out_file}")

if __name__ == "__main__":
    kill_processes()
    run_exp1_rtt_sweep()
    run_exp2_cert_delay_sweep()
    run_exp3_load_ramp()
    run_exp6_phase_breakdown()
    run_exp7_threshold_sensitivity()
    run_exp8_heatmap()
    kill_processes()
    print("\n" + "="*70)
    print("[✔] Complete 8-Experiment Suite Finished Successfully!")
    print("="*70)
