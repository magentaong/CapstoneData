
"""
starts/stops sessions for Data Brain.

keeps track of the running session, records time marks, runs the analysis workers
"""

import json
import os
import threading

from common import FS, POST_EVENT_S
from session.session import Session


class SessionManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.session = None

    def start(self, session_id=None, player_id=None, source="game"):
        with self.lock:
            if not self.active():
                self.session = Session(session_id, player_id, source)
                print(f"[session] {self.session.session_id} -> {self.session.folder}")
            return self.session

    def active(self):
        s = self.session
        return s if s and not s.finished else None

    def recorder(self):
        s = self.active()
        return s.rec if s else None

    def mark(self, s, kind, t):
        s.marks[kind] = t
        s.rec.event(t, kind)

    def add_worker(self, s, target, *args):
        w = threading.Thread(target=target, args=args, daemon=True)
        s.workers.append(w)
        w.start()

    def flush(self):
        rec = self.recorder()
        if rec:
            rec.flush()

    def finish(self, s):
        with self.lock:
            if s.finished:
                return None
            s.finished = True
        for w in s.workers:
            w.join(timeout=POST_EVENT_S + 5)
        s.rec.close()
        dump = {
            "session_id": s.session_id, "player_id": s.player_id, "source": s.source,
            "marks": s.marks,
            "calibration": s.calibration.to_dict() if s.calibration else None,
            "events": [e.to_dict() for e in s.events],
            "markers": s.markers,
            "files": {n: {"path": s.rec.path(n), "rows": r} for n, r in s.rec.rows.items()},
        }
        path = os.path.join(s.folder, "data_brain.json")
        with open(path, "w") as f:
            json.dump(dump, f, indent=2, default=float)
        print(f"[done] {s.session_id}: {s.rec.rows['raw_eeg'] / FS:.0f} s of EEG, "
              f"{len(s.events)} game events, {s.rec.rows['inputs']} inputs -> {s.folder}")
        return path
