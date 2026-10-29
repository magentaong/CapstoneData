import csv
import json
import os
import sys
import threading
import time
from bisect import bisect_left
from datetime import datetime

import numpy as np

from common import (FS, UV_PER_UNIT, EEG_LAYOUT, POST_EVENT_S, STREAM_TIMEOUT_S, OUTPUT_DIR,
                    PORT_EEG_IN, PORT_BRAIN_IN, PORT_GAME_IN, PORT_BRIDGE_CMD, PORT_PROFILER_IN,
                    Receiver, Sender, now)

CHANNELS = ["Right", "Center-Right", "Center-Left", "Left"]
#not sure if order matters need check the channels on the eeg bridge but need to connect and test
NEEURO_BANDS = ["delta", "theta", "alpha", "beta", "gamma"]
#the different brainwaves thats being analysed
STRESS_TYPES = ("time", "information", "comms", "decision", "resilience", "attention")
#can change this ^ to the different events but each event should mostly(?) link to one of the competencies
INTENSITY_MIN, INTENSITY_MAX = 1, 5
#forgot the scale 1-5 or 1-10
STRESS_EVENT_FIELDS = {"stress_type", "start_time", "end_time"}
#format receiving from the game to analyse
BUFFER_S = 2 * 60 * 60


def iso(t):
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class EEGStore:
    def __init__(self):
        self.cond = threading.Condition()
        self.chunk_t, self.chunk_x, self.chunk_end = [], [], []
        self.hr = []
        self.neeuro_states = {}
        self.neeuro_bands = None
        self.quality = [True] * len(CHANNELS)
        self.last_packet = 0.0

    def add_packet(self, t_sent, flat):
        arr = np.asarray(flat, dtype=float)
        if arr.size == 0 or arr.size % len(CHANNELS):
            return None
        if EEG_LAYOUT == "interleaved":
            x = arr.reshape(-1, len(CHANNELS)) * UV_PER_UNIT
        else:
            x = arr.reshape(len(CHANNELS), -1).T * UV_PER_UNIT
        ts = t_sent - np.arange(x.shape[0])[::-1] / FS
        with self.cond:
            if self.chunk_end and ts[0] <= self.chunk_end[-1]:
                ts = ts + (self.chunk_end[-1] + 1 / FS - ts[0])
            self.chunk_t.append(ts)
            self.chunk_x.append(x)
            self.chunk_end.append(float(ts[-1]))
            while self.chunk_end[0] < ts[-1] - BUFFER_S:
                self.chunk_t.pop(0); self.chunk_x.pop(0); self.chunk_end.pop(0)
            self.last_packet = now()
            self.cond.notify_all()
        return ts, x

    def window(self, t0, t1):
        with self.cond:
            i = bisect_left(self.chunk_end, t0)
            ts, xs = [], []
            while i < len(self.chunk_t) and self.chunk_t[i][0] < t1:
                ts.append(self.chunk_t[i]); xs.append(self.chunk_x[i]); i += 1
        if not ts:
            return np.empty(0), np.empty((0, len(CHANNELS)))
        t, x = np.concatenate(ts), np.concatenate(xs)
        m = (t >= t0) & (t < t1)
        return t[m], x[m]

    def wait_until(self, t_end, timeout):
        with self.cond:
            return self.cond.wait_for(lambda: self.chunk_end and self.chunk_end[-1] >= t_end - 1 / FS, timeout=timeout)

    def stream_ok(self):
        return now() - self.last_packet < STREAM_TIMEOUT_S


class Recorder:
    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.folder = folder
        self.lock = threading.Lock()
        self.closed = False
        self.files, self.writers, self.rows = {}, {}, {}
        self._open("raw_eeg", ["Time", "Unix Time"] + CHANNELS)
        self._open("neeuro", ["Time", "Attention", "Relaxation", "Mental Workload"] + [f"{b.capitalize()} {ch}" for ch in CHANNELS for b in NEEURO_BANDS])
        self._open("heart", ["Time", "Unix Time", "Heart Rate", "SpO2", "Detected"])
        self._open("events", ["Time", "Unix Time", "Event", "Event ID", "Stress Type", "Start", "End", "Label"])

    def _open(self, name, header):
        f = open(os.path.join(self.folder, f"{name}.csv"), "w", newline="", encoding="utf-8")
        self.files[name], self.writers[name], self.rows[name] = f, csv.writer(f), 0
        self.writers[name].writerow(header)

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

    def heart(self, t, hr, spo2, detected):
        self.write("heart", [[iso(t), f"{t:.4f}", hr, spo2, detected]])

    def event(self, t, kind, event_id="", stress_type="", start="", end="", label=""):
        self.write("events", [[iso(t), f"{t:.4f}", kind, event_id, stress_type, start, end, label]])

    def flush(self):
        with self.lock:
            for f in self.files.values():
                f.flush()

    def close(self):
        with self.lock:
            self.closed = True
            for f in self.files.values():
                f.close()


def _num(v):
    return "" if v is None else f"{v:.4f}"


def clean(x):
    # TODO: clean raw EEG (filtering) into the necessary columns 
    # (do we normalise or moving average or what, need hana input on this)
    pass


def artifact_mask(y):
    # TODO: detect blinks, movement and bad contact
    #should there be something to note when contact becomes loose halfway through game?
    pass


def features(y, hr):
    # TODO: extract the features used for stress analysis
    # basically what is being used to determine the next event
    pass


def analyse_event(t, x, hr, event):
    # TODO: analyse the event window and return (stress_type, intensity 1-5)
    pass


def stress_message(event_tag, intensity):
    if event_tag not in STRESS_TYPES:
        raise ValueError(f"event_tag must be one of {STRESS_TYPES}, got {event_tag!r}")
    if isinstance(intensity, bool):
        raise ValueError(f"intensity must be a number, got {intensity!r}")
    intensity = int(round(intensity))
    if not INTENSITY_MIN <= intensity <= INTENSITY_MAX:
        raise ValueError(f"intensity must be {INTENSITY_MIN}-{INTENSITY_MAX}, got {intensity}")
    return {"event_tag": event_tag, "intensity": intensity}


class Session:
    def __init__(self, session_id=None, player_id=None, source="game"):
        self.session_id = session_id or time.strftime("session_%Y%m%d_%H%M%S")
        self.player_id = player_id
        self.source = source
        self.marks = {}
        self.events = []
        self.markers = []
        self.folder = os.path.abspath(os.path.join(OUTPUT_DIR, self.session_id))
        self.rec = Recorder(self.folder)
        self.workers = []
        self.finished = False


class DataBrain:
    def __init__(self):
        self.store = EEGStore()
        self.session = None
        self.lock = threading.RLock()
        self.to_game = Sender(PORT_GAME_IN)
        self.to_bridge = Sender(PORT_BRIDGE_CMD)
        self.to_profiler = Sender(PORT_PROFILER_IN)
        self.running = True

    def active(self):
        s = self.session
        return s if s and not s.finished else None

    def eeg_loop(self):
        rx = Receiver(PORT_EEG_IN)
        while self.running:
            m = rx.recv()
            if not m:
                continue
            s, kind = self.active(), m.get("type")
            try:
                if kind == "eeg":
                    out = self.store.add_packet(m["t"], m["data"])
                    if out and s:
                        s.rec.eeg(*out)
                elif kind == "hr":
                    self.store.hr.append((m["t"], m["hr"]))
                    if s:
                        s.rec.heart(m["t"], m["hr"], m.get("spo2"), m.get("detected"))
                elif kind == "sdk_state":
                    self.store.neeuro_states[m["name"]] = m["value"]
                elif kind == "bands":
                    self.store.neeuro_bands = m
                    if s:
                        s.rec.neeuro(m["t"], self.store.neeuro_states, m)
                elif kind == "quality":
                    self.store.quality = list(m["channels"])
                elif kind == "evoke" and s:
                    s.rec.event(m["t"], "headset_marker", label=f"{m['ms']} ms")
                elif kind == "status" and m.get("state") not in ("battery", "device_id"):
                    print(f"[bridge] {m.get('state')} {m.get('detail', '')}")
            except (KeyError, TypeError, ValueError) as e:
                print(f"[eeg] bad {kind} message: {e!r}")

    def watchdog_loop(self):
        was_ok, last_kick, last_flush = None, 0.0, 0.0
        while self.running:
            time.sleep(0.5)
            ok = self.store.stream_ok()
            if ok != was_ok:
                print(f"[eeg] stream {'OK' if ok else 'DOWN'}")
                was_ok = ok
            if not ok and now() - last_kick > 5:
                self.to_bridge.send({"cmd": "start"})
                last_kick = now()
            s = self.active()
            if s and now() - last_flush > 2:
                s.rec.flush()
                last_flush = now()

    def game_loop(self):
        rx = Receiver(PORT_BRAIN_IN)
        while self.running:
            m = rx.recv()
            if m:
                try:
                    self.on_game_message(m)
                except Exception as e:
                    print(f"[game] error handling {m.get('type')}: {e!r}")

    def on_game_message(self, m):
        kind, t = m.get("type"), m.get("t", now())

        if kind is None and STRESS_EVENT_FIELDS <= m.keys():
            kind = "stress_event"
        print(f"[game] {kind}")

        if kind in ("calibration_start", "game_start") and not self.active():
            self.start_session(m.get("session_id"), m.get("player_id"), "game")
        s = self.active()

        if s is None:
            raise RuntimeError("no session running")

        if kind in ("calibration_start", "game_start"):
            s.marks[kind] = t
            s.rec.event(t, kind)
        elif kind == "calibration_end":
            s.marks[kind] = t
            s.rec.event(t, kind)
        elif kind == "stress_event":
            if m["stress_type"] not in STRESS_TYPES:
                print(f"[game] unknown stress_type {m['stress_type']!r}, recorded anyway")
            
            ev = {"event_id": len(s.events), "stress_type": m["stress_type"], "start": float(m["start_time"]), "end": float(m["end_time"]), "result": None}
            s.events.append(ev)
            s.rec.event(t, kind, ev["event_id"], ev["stress_type"], f"{ev['start']:.4f}", f"{ev['end']:.4f}")
            self.to_bridge.send({"cmd": "evoke"})
            w = threading.Thread(target=self.on_stress_event, args=(s, ev), daemon=True)
            s.workers.append(w)
            w.start()
        elif kind == "game_end":
            s.marks[kind] = t
            s.rec.event(t, kind)
            threading.Thread(target=self.finish, args=(s,), daemon=True).start()
        else:
            print(f"[game] unknown message type {kind!r}")

    def on_stress_event(self, s, ev):
        self.store.wait_until(ev["end"], timeout=max(0.0, ev["end"] - now()) + 2)
        t, x = self.store.window(ev["start"], ev["end"])
        result = analyse_event(t, x, self.hr_between(ev["start"], ev["end"]), ev)

        if result is None:
            return
        stress_type, intensity = result
        ev["result"] = self.send_stress(stress_type, intensity)

    def hr_between(self, t0, t1):
        return [h for (t, h) in self.store.hr if t0 <= t < t1]

    def send_stress(self, event_tag, intensity):
        msg = stress_message(event_tag, intensity)
        self.to_game.send(dict(msg), stamp=False)
        print(f"[to game] {msg}")
        return msg

    def start_session(self, session_id=None, player_id=None, source="game"):
        with self.lock:
            if not self.active():
                self.session = Session(session_id, player_id, source)
                print(f"[session] {self.session.session_id} -> {self.session.folder}")
            return self.session

    def add_marker(self, label):
        s = self.active()
        if s:
            t = now()
            s.markers.append({"t": t, "label": label})
            s.rec.event(t, "marker", label=label)
            self.to_bridge.send({"cmd": "evoke"})
            print(f"[marker] {iso(t)} {label}")

    def finish(self, s):
        with self.lock:
            if s.finished:
                return
            s.finished = True
        for w in s.workers:
            w.join(timeout=POST_EVENT_S + 5)
        s.rec.close()
        dump = {"session_id": s.session_id, "player_id": s.player_id, "source": s.source, 
                "marks": s.marks, "events": s.events, "markers": s.markers,
                "files": {n: {"path": os.path.join(s.folder, f"{n}.csv"), "rows": r} for n, r in s.rec.rows.items()}}
        
        path = os.path.join(s.folder, "data_brain.json")
        with open(path, "w") as f:
            json.dump(dump, f, indent=2, default=float)
        print(f"[done] {s.session_id}: {s.rec.rows['raw_eeg'] / FS:.0f} s of EEG, "f"{len(s.events)} stress events -> {s.folder}")
        self.to_profiler.send({"type": "report_ready", "source": "data_brain", "session_id": s.session_id, "path": path})

    def run(self, record=False, name=None):
        for f in (self.eeg_loop, self.game_loop, self.watchdog_loop):
            threading.Thread(target=f, daemon=True).start()
        self.to_bridge.send({"cmd": "start"})
        print("[data brain] EEG on 5001, game on 5002")

        if record:
            self.start_session(name, None, "manual")
            threading.Thread(target=self._markers, daemon=True).start()
        try:
            while self.running:
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        
        if self.active():
            self.finish(self.active())
            time.sleep(0.2)
        self.running = False

    def _markers(self):
        while self.running:
            try:
                line = input().strip()
            except (EOFError, KeyboardInterrupt):
                return
            if line:
                self.add_marker(line)


if __name__ == "__main__":
    args = sys.argv[1:]
    rest = [a for a in args if a != "--record"]
    DataBrain().run(record="--record" in args, name=rest[0] if rest else None)