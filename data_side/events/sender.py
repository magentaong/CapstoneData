
"""
checks result with stress_message and passes it back to game
used by data_brain.py after each event is analysed
payload should still be the event type followed and intensity update value
"""
import threading

from events.messages import stress_message


class EventSender:
    def __init__(self, transport=None):
        self._lock = threading.Lock()
        self.transport = transport

    def attach(self, transport):
        with self._lock:
            self.transport = transport

    def send_stress(self, event_tag, intensity):
        payload = stress_message(event_tag, intensity)
        with self._lock:
            transport = self.transport
        if transport is None:
            print(f"[sender] no game connected, not sent: {payload}")
            return payload
        try:
            transport(dict(payload))
        except Exception as e:
            print(f"[sender] could not send {payload}: {e!r}")
            return payload
        print(f"[sender] {payload}")
        return payload
