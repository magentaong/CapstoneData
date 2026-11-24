import random

import numpy as np

from analysis.features import features, EPOCH_S
from common import now
from eeg.cleaner import MA_WINDOW_S, clean, artifact_mask
from events.messages import STRESS_TYPES


Z_THRESHOLD = 2.0
MIN_EPOCHS = 2
MAX_IN_A_ROW = 3
START_LEVEL = 1
MIN_STEP, MAX_STEP = 0.25, 2.0


def analyse_event(feats, baseline, event):
    if baseline is None or not feats:
        return None
    delta = np.asarray(feats["delta"], dtype=float)
    if np.count_nonzero(~np.isnan(delta)) < MIN_EPOCHS:
        return None
    return baseline.relative({"delta": float(np.nanmax(delta))})


def stress_result(event, z):
    if z is None or z < Z_THRESHOLD:
        return None
    return event.stress_type, min(5, int(z - Z_THRESHOLD) + 1)


def level_step(z):
    if z is None:
        return (MIN_STEP + MAX_STEP) / 2
    calm = min(1.0, max(0.0, 1 - z / (2 * Z_THRESHOLD)))
    return MIN_STEP + (MAX_STEP - MIN_STEP) * calm


def next_event(events, event):
    past = [e for e in events if e.event_id <= event.event_id]
    run = 1
    while run < len(past) and past[-run - 1].stress_type == event.stress_type:
        run += 1
    limit = random.Random(past[-run].start).randint(1, MAX_IN_A_ROW)
    tag = event.stress_type
    if run >= limit:
        others = [t for t in STRESS_TYPES if t != tag]
        played = {t: sum(e.stress_type == t for e in past) for t in others}
        tag = random.choice([t for t in others if played[t] == min(played.values())])
    level = START_LEVEL + sum(level_step(e.score) for e in past if e.stress_type == tag)
    return tag, min(5, int(level + 0.5))


class GameplayAnalysis:
    def __init__(self, collector, baseline):
        self.collector = collector
        self.baseline = baseline

    def analyse(self, event):
        pad = MA_WINDOW_S // 2
        self.collector.wait_until(event.end + pad, timeout=max(0.0, event.end + pad - now()) + 2)
        t, x = self.collector.window(event.start - pad, event.end + pad)
        feats = features(x, artifact_mask(x))
        smooth = clean(feats["delta"], EPOCH_S)
        n = int(pad / EPOCH_S)
        feats["delta"] = smooth[n:len(smooth) - n]
        return analyse_event(feats, self.baseline.get(), event)
