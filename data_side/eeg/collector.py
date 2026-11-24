"""
receives everything the EEG bridge sends and keeps it ready for the Data Brain

EEG goes into the buffer, neeuro values and contact quality kept here
restarts bridge stream if data stops, created by data_brain.py and used by calibration and analysis
"""

import threading
import time

from common import CHANNELS, PORT_EEG_IN, PORT_BRIDGE_CMD, STREAM_TIMEOUT_S, Receiver, Sender, now
from eeg.buffer import EEGBuffer


class EEGCollector:
    def __init__(self, get_recorder):
        self.buffer = EEGBuffer()
        self.get_recorder = get_recorder
        self.to_bridge = Sender(PORT_BRIDGE_CMD)
        self.neeuro_states = {}
        self.neeuro_bands = None
        self.quality = [True] * len(CHANNELS)
        self.running = False

    def start(self):
        self.running = True
        for f in (self._listen, self._watchdog):
            threading.Thread(target=f, daemon=True).start()
        self.command("start")

    def stop(self):
        self.running = False

    def command(self, cmd):
        self.to_bridge.send({"cmd": cmd})

    def stream_ok(self):
        return now() - self.buffer.last_packet < STREAM_TIMEOUT_S

    def window(self, t0, t1):
        return self.buffer.window(t0, t1)

    def wait_until(self, t_end, timeout):
        return self.buffer.wait_until(t_end, timeout)

    def _listen(self):
        rx = Receiver(PORT_EEG_IN)
        while self.running:
            m = rx.recv()
            if not m:
                continue
            rec, kind = self.get_recorder(), m.get("type")
            try:
                if kind == "eeg":
                    out = self.buffer.add_packet(m["t"], m["data"])
                    if out and rec:
                        rec.eeg(*out)
                elif kind == "sdk_state":
                    self.neeuro_states[m["name"]] = m["value"]
                elif kind == "bands":
                    self.neeuro_bands = m
                    if rec:
                        rec.neeuro(m["t"], self.neeuro_states, m)
                elif kind == "quality":
                    self.quality = list(m["channels"])
                elif kind == "evoke" and rec:
                    rec.event(m["t"], "headset_marker", label=f"{m['ms']} ms")
                elif kind == "status" and m.get("state") not in ("battery", "device_id"):
                    print(f"[bridge] {m.get('state')} {m.get('detail', '')}")
            except (KeyError, TypeError, ValueError) as e:
                print(f"[eeg] bad {kind} message: {e!r}")

    def _watchdog(self):
        was_ok, last_kick = None, 0.0
        while self.running:
            time.sleep(0.5)
            ok = self.stream_ok()
            if ok != was_ok:
                print(f"[eeg] stream {'OK' if ok else 'DOWN'}")
                was_ok = ok
            if not ok and now() - last_kick > 5:
                self.command("start")
                last_kick = now()
