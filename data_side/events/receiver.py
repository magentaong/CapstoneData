"""
works out the message type and passes it to the matching DataBrain handler
bad or unknown messages are printed and skipped (probably no issues once agree on payload formats)
"""

from events.messages import unwrap


class EventReceiver:
    def __init__(self, handler):
        self.handler = handler
        self.routes = {
            "calibration_start": handler.on_calibration_start,
            "calibration_end": handler.on_calibration_end,
            "game_start": handler.on_game_start,
            "game_end": handler.on_game_end,
            "event_started": self._started,
            "event_ended": self._ended,
            "input": handler.on_input,
        }
        self.pending = {}

    def handle(self, message):
        if not isinstance(message, dict):
            print(f"[receiver] ignored non-object message: {message!r}")
            return
        kind, m = unwrap(message)
        route = self.routes.get(kind)
        if route is None:
            print(f"[receiver] unknown message type {kind!r}")
            return
        print(f"[receiver] {kind}")
        try:
            route(m)
        except Exception as e:
            print(f"[receiver] error handling {kind}: {e!r}")

    def _started(self, m):
        self.pending[m["event_id"]] = m
        self.handler.on_event_started(m)

    def _ended(self, m):
        started = self.pending.pop(m["event_id"], None)
        if started is None:
            print(f"[receiver] EVENT_ENDED without EVENT_STARTED for {m['event_id']!r}, skipped")
            return
        self.handler.on_game_event(started, m)
