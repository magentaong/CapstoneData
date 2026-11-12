
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
    # TODO: overall profile analysis at game end
    pass


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

