
"""
builds overall end profile after the whole game finish
"""

import json
import os

from calibration.profile import CalibrationProfile
from profiling.input_logger import load_inputs, summarise


def load(path):
    with open(path) as f:
        return json.load(f)


def build_profile(brain, inputs, calib):
    by_type = {}
    for e in brain.get("events", []):
        d = by_type.setdefault(e["stress_type"], {"events": 0, "stressed": 0, "intensity": [], "by_level": {}})
        d["events"] += 1
        lv = d["by_level"].setdefault(str(e.get("level")), {"events": 0, "stressed": 0})
        lv["events"] += 1
        if e.get("result"):
            d["stressed"] += 1
            lv["stressed"] += 1
            d["intensity"].append(e["result"]["intensity"])
    for d in by_type.values():
        d["stress_rate"] = d["stressed"] / d["events"]
        d["avg_intensity"] = sum(d["intensity"]) / len(d["intensity"]) if d["intensity"] else None
        del d["intensity"]
        for lv in d["by_level"].values():
            lv["stress_rate"] = lv["stressed"] / lv["events"]
        d["by_level"] = dict(sorted(d["by_level"].items()))
    marks = brain.get("marks", {})
    played = marks.get("game_end", 0) - marks.get("game_start", 0) if "game_start" in marks else None
    return {
        "session_id": brain.get("session_id"),
        "player_id": brain.get("player_id"),
        "game_length_s": played,
        "difficulty": calib.difficulty if calib else None,
        "calibrated": bool(calib and calib.baseline),
        "stress_by_type": by_type,
        "most_stressful": max(by_type, key=lambda k: by_type[k]["stress_rate"]) if by_type else None,
        "inputs": inputs,
    }


def write_profile(brain_path):
    brain = load(brain_path)
    calib = CalibrationProfile.from_dict(brain["calibration"]) if brain.get("calibration") else None
    inputs_file = brain.get("files", {}).get("inputs")
    rows = load_inputs(inputs_file["path"]) if inputs_file else []
    inputs = summarise(rows, brain.get("events", []))
    profile = build_profile(brain, inputs, calib)
    if profile is None:
        return None
    out = os.path.join(os.path.dirname(os.path.abspath(brain_path)), "profile.json")
    with open(out, "w") as f:
        json.dump(profile, f, indent=2)
    return out

