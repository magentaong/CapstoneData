from analysis.features import features
from common import now
from eeg.cleaner import clean, artifact_mask


def analyse_event(feats, bad, baseline, event):
    # TODO: analyse the event window and return (stress_type, intensity 1-5)
    pass


class GameplayAnalysis:
    def __init__(self, collector, baseline):
        self.collector = collector
        self.baseline = baseline

    def analyse(self, event):
        self.collector.wait_until(event.end, timeout=max(0.0, event.end - now()) + 2)
        t, x = self.collector.window(event.start, event.end)
        y = clean(x)
        bad = artifact_mask(y)
        feats = features(y, self.collector.hr_between(event.start, event.end))
        return analyse_event(feats, bad, self.baseline.get(), event)
