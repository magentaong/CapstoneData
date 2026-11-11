"""
holds the calibration profile throughout the game

gameplay analysis side reads the profile from here
this is set when calibration finishes and cleared when whole session ends
"""
import threading


class BaselineReceiver:
    def __init__(self):
        self._lock = threading.Lock()
        self._profile = None

    def set(self, profile):
        with self._lock:
            self._profile = profile

    def get(self):
        with self._lock:
            return self._profile

    def clear(self):
        self.set(None)
