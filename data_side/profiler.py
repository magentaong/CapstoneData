import csv
import json
import os

from common import PORT_PROFILER_IN, Receiver

CHANNELS = ["Right", "Center-Right", "Center-Left", "Left"]


class CalibrationProfile:
    def __init__(self):
        self.difficulty = 1
        self.start = self.end = None

    def fit(self, t, x, hr):
        # TODO: build the player baseline to the difficulty multiplier
        pass

    def relative(self, feats):
        # TODO: express features relative to the player's baseline
        pass

    def to_dict(self):
        return {"difficulty": self.difficulty, "start": self.start, "end": self.end}


def load(path):
    with open(path) as f:
        return json.load(f)


def load_window(path, t0, t1, columns):
    t, rows = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = float(r["Unix Time"])
            if t0 <= ts < t1:
                t.append(ts)
                rows.append([float(r[c]) if r[c] != "" else None for c in columns])
    return t, rows


def calibrate(brain):
    calib = CalibrationProfile()
    marks = brain.get("marks", {})
    if "calibration_end" not in marks:
        return calib
    calib.start = marks.get("calibration_start", marks["calibration_end"] - 20)
    calib.end = marks["calibration_end"]
    files = brain["files"]
    t, x = load_window(files["raw_eeg"]["path"], calib.start, calib.end, CHANNELS)
    _, hr = load_window(files["heart"]["path"], calib.start, calib.end, ["Heart Rate"])
    calib.fit(t, x, [h[0] for h in hr])
    return calib


def load_input_logger(session_id):
    # TODO: receive the input logger stuff
    pass


def build_profile(brain, inputs, calib):
    # TODO: overall profile analysis at game end
    pass


def write_profile(brain_path):
    brain = load(brain_path)
    calib = calibrate(brain)
    inputs = load_input_logger(brain["session_id"])
    profile = build_profile(brain, inputs, calib)
    if profile is None:
        return None
    out = os.path.join(os.path.dirname(os.path.abspath(brain_path)), "profile.json")
    with open(out, "w") as f:
        json.dump(profile, f, indent=2)
    return out


def run():
    rx = Receiver(PORT_PROFILER_IN)
    print("[profiler] waiting for session reports on 5006")
    while True:
        m = rx.recv()
        if not m or m.get("type") != "report_ready":
            continue
        print(f"[profiler] report for {m.get('session_id')}")
        try:
            out = write_profile(m["path"])
        except (OSError, KeyError, ValueError) as e:
            print(f"[profiler] could not read report: {e!r}")
            continue
        if out:
            print(f"[profiler] wrote {out}")
        else:
            print("[profiler] no profile built")


if __name__ == "__main__":
    run()