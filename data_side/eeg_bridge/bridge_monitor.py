import csv
import json
import os
import socket
import sys
import threading
import time
from collections import deque
from datetime import datetime

try:
    import numpy as np
except ImportError:
    np = None

PORT_DATA = 5001
PORT_CMD = 5005
FS = 250
UV_PER_UNIT = 0.61
CHANNELS = ["Right", "Center-Right", "Center-Left", "Left"]
SHORT = ["R", "CR", "CL", "L"]
CSV_BANDS = ["delta", "theta", "alpha", "beta", "gamma"]
BANDS = [("delta", 1, 4), ("theta", 4, 8),
         ("alpha", 8, 12), ("low_alpha", 8, 10), ("high_alpha", 10, 12),
         ("beta", 12, 30), ("low_beta", 12, 20), ("high_beta", 20, 30),
         ("gamma", 30, 40)]
LABELS = {"delta": "delta", "theta": "theta", "alpha": "alpha", "low_alpha": "loAlpha",
          "high_alpha": "hiAlpha", "beta": "beta", "low_beta": "loBeta", "high_beta": "hiBeta",
          "gamma": "gamma"}
MAIN = [0, 1, 2, 5, 8]
COMMANDS = {"s": "start", "x": "stop", "e": "evoke", "i": "impedance_on", "d": "impedance_off", "p": "ping"}

HELP = """b  band table on/off
a  raw rows: shares / power in uV2
s  start EEG    x  stop EEG    e  evoke marker
i  impedance on d  impedance off
p  ping         q  quit"""

lock = threading.Lock()
stats = {"packets": 0, "bad": 0, "ch_min": None, "ch_max": None, "lag": []}
latest = {}
raw = [deque(maxlen=2 * FS) for _ in CHANNELS]
view = {"bands": False, "absolute": False}
running = True


class Recorder:

    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, time.strftime("recording_%Y%m%d_%H%M%S.csv"))
        self.f = open(self.path, "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        header = ["Time", "Attention", "Relaxation", "Mental Workload"]
        header += [f"{b.capitalize()} {ch}" for ch in CHANNELS for b in CSV_BANDS]
        self.w.writerow(header)
        self.rows = 0

    def write(self, t, states, bands):
        names = bands["names"]
        row = [datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]]
        row += [fmt(states.get(k)) for k in ("attention", "relaxation", "workload")]
        for c in range(len(CHANNELS)):
            vals = bands["values"][c] if c < len(bands["values"]) else []
            for b in CSV_BANDS:
                i = names.index(b) if b in names else None
                row.append(fmt(vals[i] if i is not None and i < len(vals) else None))
        self.w.writerow(row)
        self.f.flush()
        self.rows += 1

    def close(self):
        self.f.close()


def fmt(v):
    return "" if v is None else f"{v:.4f}"


recorder = None


def receive_loop(sock):
    while running:
        try:
            data, _ = sock.recvfrom(65536)
        except socket.timeout:
            continue
        try:
            m = json.loads(data.decode())
        except ValueError:
            with lock:
                stats["bad"] += 1
            continue
        kind = m.get("type")
        with lock:
            if kind == "eeg":
                vals = m.get("data", [])
                if len(vals) != 200:
                    stats["bad"] += 1
                    continue
                stats["packets"] += 1
                stats["lag"].append(time.time() - m["t"])
                for c in range(4):
                    seg = [v * UV_PER_UNIT for v in vals[c * 50:(c + 1) * 50]]
                    raw[c].extend(seg)
                    lo, hi = min(seg), max(seg)
                    if stats["ch_min"] is None:
                        stats["ch_min"], stats["ch_max"] = [lo] * 4, [hi] * 4
                    stats["ch_min"][c] = min(stats["ch_min"][c], lo)
                    stats["ch_max"][c] = max(stats["ch_max"][c], hi)
            elif kind == "status":
                print(f"\n[status] {m.get('state')} {m.get('detail', '')}")
            elif kind == "evoke":
                print(f"\n[evoke] marker recorded at {m.get('ms')} ms after first EEG packet")
            elif kind in ("sdk_state", "flag"):
                latest[m["name"]] = m["value"]
            elif kind in ("hr", "quality", "impedance", "bands"):
                latest[kind] = m
                if kind == "bands" and recorder:
                    recorder.write(m["t"], latest, m)


def raw_band_table(absolute: bool):
    if np is None or any(len(r) < 2 * FS for r in raw):
        return None
    rows = []
    w = np.hanning(2 * FS)
    for r in raw:
        x = np.asarray(r) - np.mean(r)
        psd = np.abs(np.fft.rfft(x * w)) ** 2 / (FS * np.sum(w ** 2))
        psd[1:-1] *= 2
        f = np.fft.rfftfreq(len(x), 1 / FS)
        df = f[1] - f[0]
        p = np.array([psd[(f >= lo) & (f < hi)].sum() * df for _, lo, hi in BANDS])
        if not absolute:
            total = p[MAIN].sum()
            p = p / total if total > 0 else p
        rows.append(p)
    return rows


def print_band_table(snap, raw_rows, absolute):
    print("\n" + " " * 20 + "".join(f"{LABELS[n]:>9}" for n, _, _ in BANDS))
    bands = snap.get("bands")
    if bands:
        names = bands["names"]
        for c, row in enumerate(bands["values"]):
            cells = []
            for n, _, _ in BANDS:
                i = names.index(n) if n in names else None
                cells.append(f"{row[i]:9.2f}" if i is not None and i < len(row) else f"{'-':>9}")
            print(f"{'neeuro ' + (CHANNELS[c] if c < 4 else str(c)):<20}" + "".join(cells))
    else:
        print("neeuro     (no band data from the SDK yet)")
    if raw_rows is not None:
        cell = "{:9.1f}" if absolute else "{:9.2f}"
        for c, row in enumerate(raw_rows):
            print(f"{'raw    ' + CHANNELS[c]:<20}" + "".join(cell.format(v) for v in row))
        print("                    neeuro = share of power (SDK) | raw = "
              + ("power in µV² (press a for shares)" if absolute else "share of power (press a for µV²)"))
    elif np is None:
        print("raw        (pip install numpy to also see bands calculated from the raw EEG)")
    else:
        print("raw        (collecting 2 s of EEG...)")


def summary_line(n, bad, lo, hi, lag, snap):
    parts = [f"EEG {n} pkt/s" + ("  (expect 5)" if n not in (4, 5, 6) else "")]
    if lo:
        parts.append("µV range " + "  ".join(f"{SHORT[c]} {hi[c] - lo[c]:5.0f}" for c in range(4)))
    if lag is not None:
        parts.append(f"delay {lag * 1000:.0f} ms")
    if "hr" in snap:
        parts.append(f"HR {snap['hr'].get('hr')} SpO2 {snap['hr'].get('spo2')}")
    if "quality" in snap:
        parts.append("contact " + "".join("✓" if ok else "✗" for ok in snap["quality"]["channels"]))
    if "impedance" in snap:
        parts.append("impedance kΩ " + " ".join(f"{k:.0f}" for k in snap["impedance"]["kohm"]))
    if "signal_ready" in snap:
        parts.append(f"worn OK {snap['signal_ready']}")
    if snap.get("connection_ok") is False:
        parts.append("BLUETOOTH DATA LOSS")
    if "attention" in snap:
        parts.append(f"neeuro att {snap['attention']:.2f} rel {snap.get('relaxation', 0):.2f} "
                     f"work {snap.get('workload', 0):.2f}")
    if bad:
        parts.append(f"{bad} bad msgs")
    return " | ".join(parts) if n or len(parts) > 1 else "waiting for the bridge... (is EegBridge.exe running?)"


def report_loop():
    while running:
        time.sleep(1)
        with lock:
            n, bad = stats["packets"], stats["bad"]
            lo, hi = stats["ch_min"], stats["ch_max"]
            lag = sum(stats["lag"]) / len(stats["lag"]) if stats["lag"] else None
            stats.update(packets=0, bad=0, ch_min=None, ch_max=None, lag=[])
            snap = dict(latest)
            raw_rows = raw_band_table(view["absolute"]) if view["bands"] else None
        if view["bands"]:
            print_band_table(snap, raw_rows, view["absolute"])
        else:
            print(summary_line(n, bad, lo, hi, lag, snap))


def main():
    global running, recorder
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        rx.bind(("127.0.0.1", PORT_DATA))
    except OSError:
        print(f"Port {PORT_DATA} is in use. Close data_brain.py (or another monitor) first.")
        return
    rx.settimeout(0.5)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if "--no-record" not in sys.argv:
        recorder = Recorder(os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings"))

    threading.Thread(target=receive_loop, args=(rx,), daemon=True).start()
    threading.Thread(target=report_loop, daemon=True).start()
    print(HELP)
    print()
    if recorder:
        print(f"Recording Neeuro values to {recorder.path}")
        print()

    try:
        while True:
            key = input().strip().lower()
            if key == "q":
                break
            if key == "a":
                view["absolute"] = not view["absolute"]
                print(f"-> raw rows show {'power in µV²' if view['absolute'] else 'shares'}")
            elif key == "b":
                view["bands"] = not view["bands"]
                print(f"-> {'band table' if view['bands'] else 'summary'} view")
            elif key in COMMANDS:
                tx.sendto(json.dumps({"cmd": COMMANDS[key]}).encode(), ("127.0.0.1", PORT_CMD))
                print(f"-> sent '{COMMANDS[key]}'")
            elif key:
                print("commands: b a s x e i d p q")
    except (KeyboardInterrupt, EOFError):
        pass
    running = False
    if recorder:
        with lock:
            recorder.close()
        print(f"Saved {recorder.rows} rows to {recorder.path}")


if __name__ == "__main__":
    main()
