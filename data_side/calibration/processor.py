"""
creates player calibration profile when calibration ends

takes the EEG and heart rate (probably will drop this, but minor changes)
cleans the EEG and fits a new profile from it.
"""

from calibration.profile import CalibrationProfile
from eeg.cleaner import clean

DEFAULT_CALIBRATION_S = 20.0


class CalibrationProcessor:
    def __init__(self, collector, default_s=DEFAULT_CALIBRATION_S):
        self.collector = collector
        self.default_s = default_s

    def process(self, start, end):
        if start is None:
            start = end - self.default_s
        self.collector.wait_until(end, timeout=2)
        t, x = self.collector.window(start, end)
        profile = CalibrationProfile(start, end)
        profile.fit(t, clean(x), self.collector.hr_between(start, end))
        return profile
