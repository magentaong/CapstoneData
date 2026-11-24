"""
stores the player calibration: start and end time, difficulty and baseline

fit() works out the baseline from the calibration data
relative() compares gameplay against ^^

this is used to shared with gameplay analysis and saved for end game profiler
"""

import numpy as np

MIN_STD = 0.02


class CalibrationProfile:
    def __init__(self, start=None, end=None, difficulty=1, baseline=None):
        self.start = start
        self.end = end
        self.difficulty = difficulty
        self.baseline = baseline or {}

    def fit(self, delta):
        good = [d for d in delta if not np.isnan(d)]
        if len(good) < 3:
            print(f"[calibration] only {len(good)} clean seconds, no baseline")
            return
        self.baseline = {"delta_mean": float(np.mean(good)), "delta_std": float(np.std(good)),
                         "epochs": len(good)}
        # TODO: set self.difficulty (1-5) from the calibration, stays at the default for now

    def relative(self, feats):
        if "delta_mean" not in self.baseline:
            return None
        std = max(self.baseline["delta_std"], MIN_STD)
        return (feats["delta"] - self.baseline["delta_mean"]) / std

    def to_dict(self):
        return {"difficulty": self.difficulty, "start": self.start, "end": self.end, "baseline": self.baseline}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("start"), d.get("end"), d.get("difficulty", 1), d.get("baseline"))
