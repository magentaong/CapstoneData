"""
cleans the raw EEG and flags unusable samples before analysis
used by calibration and gameplay analysis on the EEG from the collector

artifact_mask is if can implement, because bad contact with EEG sometimes still
gives data but those samples should not be used in the analysis since unstable readings (?)
"""

import numpy as np

from common import FS

MA_WINDOW_S = 5
MAX_UV = 100.0
FLAT_UV = 0.5
PAD_S = 0.2


def clean(values, step_s=1.0, window_s=MA_WINDOW_S):
    v = np.asarray(values, dtype=float)
    half = int(round(window_s / step_s)) // 2
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        part = v[max(0, i - half):i + half + 1]
        if np.any(~np.isnan(part)):
            out[i] = np.nanmean(part)
    return out


def artifact_mask(x):
    x = np.asarray(x, dtype=float)
    bad = np.zeros(len(x), dtype=bool)
    if len(x) == 0:
        return bad
    for i in range(0, len(x), FS):
        block = x[i:i + FS]
        bad[i:i + FS] |= (np.abs(block - block.mean(axis=0)) > MAX_UV).any(axis=1)
    step = FS // 5
    for i in range(0, len(x), step):
        if (x[i:i + step].std(axis=0) < FLAT_UV).any():
            bad[i:i + step] = True
    pad = int(PAD_S * FS)
    for i in np.flatnonzero(bad):
        bad[max(0, i - pad):i + pad + 1] = True
    return bad
