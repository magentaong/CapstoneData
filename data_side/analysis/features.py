import numpy as np

from common import FS

EPOCH_S = 1.0
DELTA = (0.5, 4.0)
TOTAL = (0.5, 40.0)


def band_share(epoch, band, total=TOTAL):
    epoch = epoch - epoch.mean(axis=0)
    f = np.fft.rfftfreq(len(epoch), 1 / FS)
    p = np.abs(np.fft.rfft(epoch * np.hanning(len(epoch))[:, None], axis=0)) ** 2
    num = p[(f >= band[0]) & (f < band[1])].sum(axis=0)
    den = p[(f >= total[0]) & (f < total[1])].sum(axis=0)
    return float(np.mean(num / np.maximum(den, 1e-12)))


def features(x, bad):
    n = int(EPOCH_S * FS)
    x = np.asarray(x, dtype=float)
    delta = [np.nan if np.any(bad[i:i + n]) else band_share(x[i:i + n], DELTA)
             for i in range(0, len(x) - n + 1, n)]
    return {"delta": delta}
