"""
stores the player calibration: start and end time, difficulty and baseline

fit() works out the baseline from the calibration data
relative() compares gameplay against ^^

this is used to shared with gameplay analysis and saved for end game profiler
"""

class CalibrationProfile:
    def __init__(self, start=None, end=None, difficulty=1, baseline=None):
        self.start = start
        self.end = end
        self.difficulty = difficulty
        self.baseline = baseline or {}

    def fit(self, t, y, hr):
        # TODO: build the player baseline to the difficulty multiplier
        pass

    def relative(self, feats):
        # TODO: express features relative to the player's baseline
        pass

    def to_dict(self):
        return {"difficulty": self.difficulty, "start": self.start, "end": self.end, "baseline": self.baseline}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("start"), d.get("end"), d.get("difficulty", 1), d.get("baseline"))
