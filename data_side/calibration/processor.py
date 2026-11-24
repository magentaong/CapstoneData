"""
creates player calibration profile when calibration ends

takes the EEG from the calibration period, measures delta each second,
smooths it with the moving average and fits a new profile from it.
"""

from analysis.features import features, EPOCH_S
from calibration.profile import CalibrationProfile
from eeg.cleaner import MA_WINDOW_S, clean, artifact_mask

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
        feats = features(x, artifact_mask(x))
        smooth = clean(feats["delta"], EPOCH_S)
        n = int(MA_WINDOW_S // 2 / EPOCH_S)
        profile.fit(smooth[n:len(smooth) - n])
        return profile
