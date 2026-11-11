"""
keeps the last 30 minutes of EEG in memory, with timestamp of samples
"""

import threading
from bisect import bisect_left
import numpy as np

from common import FS, CHANNELS, UV_PER_UNIT, EEG_LAYOUT, now

BUFFER_S = 30 * 60 
# adjustable value, but since game and everything takes ~20mins
# then total experience including setup take 30 (?)


class EEGBuffer:
    def __init__(self, buffer_s=BUFFER_S):
        self.buffer_s = buffer_s
        self.cond = threading.Condition()
        self.chunk_t, self.chunk_x, self.chunk_end = [], [], []
        self.last_packet = 0.0

    def add_packet(self, t_sent, flat):
        arr = np.asarray(flat, dtype=float)
        if arr.size == 0 or arr.size % len(CHANNELS):
            return None
        if EEG_LAYOUT == "interleaved":
            x = arr.reshape(-1, len(CHANNELS)) * UV_PER_UNIT
        else:
            x = arr.reshape(len(CHANNELS), -1).T * UV_PER_UNIT
        ts = t_sent - np.arange(x.shape[0])[::-1] / FS
        with self.cond:
            if self.chunk_end and ts[0] <= self.chunk_end[-1]:
                ts = ts + (self.chunk_end[-1] + 1 / FS - ts[0])
            self.chunk_t.append(ts)
            self.chunk_x.append(x)
            self.chunk_end.append(float(ts[-1]))
            while self.chunk_end[0] < ts[-1] - self.buffer_s:
                self.chunk_t.pop(0)
                self.chunk_x.pop(0)
                self.chunk_end.pop(0)
            self.last_packet = now()
            self.cond.notify_all()
        return ts, x

    def window(self, t0, t1):
        with self.cond:
            i = bisect_left(self.chunk_end, t0)
            ts, xs = [], []
            while i < len(self.chunk_t) and self.chunk_t[i][0] < t1:
                ts.append(self.chunk_t[i])
                xs.append(self.chunk_x[i])
                i += 1
        if not ts:
            return np.empty(0), np.empty((0, len(CHANNELS)))
        t, x = np.concatenate(ts), np.concatenate(xs)
        m = (t >= t0) & (t < t1)
        return t[m], x[m]

    def wait_until(self, t_end, timeout):
        with self.cond:
            return self.cond.wait_for(lambda: self.chunk_end and self.chunk_end[-1] >= t_end - 1 / FS, timeout=timeout)
