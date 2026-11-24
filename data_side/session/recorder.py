import csv
import os
import threading
from datetime import datetime

from common import CHANNELS

NEEURO_BANDS = ["delta", "theta", "alpha", "beta", "gamma"]
#the different brainwaves thats being analysed


def iso(t):
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _num(v):
    return "" if v is None else f"{v:.4f}"


class Recorder:
    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.folder = folder
        self.lock = threading.Lock()
        self.closed = False
        self.files, self.writers, self.rows = {}, {}, {}
        self._open("raw_eeg", ["Time", "Unix Time"] + CHANNELS)
        self._open("neeuro", ["Time", "Attention", "Relaxation", "Mental Workload"] + [f"{b.capitalize()} {ch}" for ch in CHANNELS for b in NEEURO_BANDS])
        self._open("events", ["Time", "Unix Time", "Event", "Event ID", "Stress Type", "Start", "End", "Label"])
        self._open("inputs", ["Time", "Unix Time", "Action", "Details"])

    def _open(self, name, header):
        f = open(os.path.join(self.folder, f"{name}.csv"), "w", newline="", encoding="utf-8")
        self.files[name], self.writers[name], self.rows[name] = f, csv.writer(f), 0
        self.writers[name].writerow(header)

    def path(self, name):
        return os.path.join(self.folder, f"{name}.csv")

    def write(self, name, rows):
        with self.lock:
            if not self.closed:
                self.writers[name].writerows(rows)
                self.rows[name] += len(rows)

    def eeg(self, ts, x):
        self.write("raw_eeg", [[iso(t), f"{t:.4f}"] + [f"{v:.2f}" for v in row] for t, row in zip(ts, x)])

    def neeuro(self, t, states, bands):
        row = [iso(t)] + [_num(states.get(k)) for k in ("attention", "relaxation", "workload")]
        for c in range(len(CHANNELS)):
            vals = bands["values"][c] if c < len(bands["values"]) else []
            for b in NEEURO_BANDS:
                i = bands["names"].index(b) if b in bands["names"] else None
                row.append(_num(vals[i] if i is not None and i < len(vals) else None))
        self.write("neeuro", [row])

    def event(self, t, kind, event_id="", stress_type="", start="", end="", label=""):
        self.write("events", [[iso(t), f"{t:.4f}", kind, event_id, stress_type, start, end, label]])

    def input(self, t, action, details):
        self.write("inputs", [[iso(t), f"{t:.4f}", action, details]])

    def flush(self):
        with self.lock:
            if not self.closed:
                for f in self.files.values():
                    f.flush()

    def close(self):
        with self.lock:
            self.closed = True
            for f in self.files.values():
                f.close()
