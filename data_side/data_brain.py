
"""
creates every component and connects them
receives EEG from the bridge and game messages over the WebSocket
builds the calibration profile, analyses each event and sends stress result back
when game_end it writes the session report and builds the end player profile.
"""

import sys
import threading
import time

from analysis.gameplay import GameplayAnalysis
from calibration.baseline import BaselineReceiver
from calibration.processor import CalibrationProcessor
from common import now
from eeg.collector import EEGCollector
from events.messages import STRESS_TYPES, parse_game_event
from events.receiver import EventReceiver
from events.sender import EventSender
from profiling.input_logger import InputLogger
from profiling.profiler import write_profile
from session.manager import SessionManager
from session.recorder import iso
from transport.websocket import WebSocketGameTransport


class DataBrain:
    def __init__(self):
        self.sessions = SessionManager()
        self.collector = EEGCollector(self.sessions.recorder)
        self.baseline = BaselineReceiver()
        self.calibration = CalibrationProcessor(self.collector)
        self.analysis = GameplayAnalysis(self.collector, self.baseline)
        self.receiver = EventReceiver(self)
        self.sender = EventSender()
        self.input_logger = InputLogger(self.sessions.active)
        self.transport = None
        self.running = True

    def _start_or_active(self, m):
        return self.sessions.active() or self.sessions.start(m.get("session_id"), m.get("player_id"), "game")

    def _require_active(self):
        s = self.sessions.active()
        if s is None:
            raise RuntimeError("no session running")
        return s

    def on_calibration_start(self, m):
        self.sessions.mark(self._start_or_active(m), "calibration_start", m.get("t", now()))

    def on_calibration_end(self, m):
        s = self._require_active()
        self.sessions.mark(s, "calibration_end", m.get("t", now()))
        self.sessions.add_worker(s, self.run_calibration, s)

    def on_game_start(self, m):
        self.sessions.mark(self._start_or_active(m), "game_start", m.get("t", now()))

    def on_game_end(self, m):
        s = self._require_active()
        self.sessions.mark(s, "game_end", m.get("t", now()))
        threading.Thread(target=self.finish, args=(s,), daemon=True).start()

    def on_game_event(self, m):
        s = self._require_active()
        if m["stress_type"] not in STRESS_TYPES:
            print(f"[receiver] unknown stress_type {m['stress_type']!r}, recorded anyway")
        ev = parse_game_event(m, len(s.events), now())
        s.events.append(ev)
        s.rec.event(ev.received, "game_event", ev.event_id, ev.stress_type, f"{ev.start:.4f}", f"{ev.end:.4f}")
        self.sessions.add_worker(s, self.analyse_and_send, s, ev)

    def run_calibration(self, s):
        profile = self.calibration.process(s.marks.get("calibration_start"), s.marks["calibration_end"])
        s.calibration = profile
        self.baseline.set(profile)

    def analyse_and_send(self, s, ev):
        result = self.analysis.analyse(ev)
        if result is None:
            return
        event_tag, intensity = result
        ev.result = self.sender.send_stress(event_tag, intensity)
        s.rec.event(now(), "stress_sent", ev.event_id, ev.result["event_tag"], label=f"intensity {ev.result['intensity']}")

    def add_marker(self, label):
        s = self.sessions.active()
        if s:
            t = now()
            s.markers.append({"t": t, "label": label})
            s.rec.event(t, "marker", label=label)
            self.collector.command("evoke")
            print(f"[marker] {iso(t)} {label}")

    def run_profiler(self, path):
        try:
            out = write_profile(path)
        except (OSError, KeyError, ValueError) as e:
            print(f"[profiler] could not build profile: {e!r}")
            return
        print(f"[profiler] wrote {out}" if out else "[profiler] no profile built")

    def finish(self, s):
        path = self.sessions.finish(s)
        self.baseline.clear()
        if path:
            self.run_profiler(path)

    def run(self, record=False, name=None):
        # Start the EEG collector and the WebSocket, then run until Ctrl+C
        self.collector.start()
        self.transport = WebSocketGameTransport(self.receiver.handle, self.input_logger.handle)
        self.transport.start()
        self.sender.attach(self.transport.send)
        print("[data brain] running")
        if record:
            self.sessions.start(name, None, "manual")
            threading.Thread(target=self._markers, daemon=True).start()
        last_flush = 0.0
        try:
            while self.running:
                time.sleep(0.2)
                if now() - last_flush > 2:
                    self.sessions.flush()
                    last_flush = now()
        except KeyboardInterrupt:
            pass
        s = self.sessions.active()
        if s:
            self.finish(s)
            time.sleep(0.2)
        self.running = False
        self.transport.stop()
        self.collector.stop()

    def _markers(self):
        while self.running:
            try:
                line = input().strip()
            except (EOFError, KeyboardInterrupt):
                return
            if line:
                self.add_marker(line)


if __name__ == "__main__":
    args = sys.argv[1:]
    rest = [a for a in args if a != "--record"]
    DataBrain().run(record="--record" in args, name=rest[0] if rest else None)
