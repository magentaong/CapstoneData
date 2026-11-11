"""
works out the message type and passes it to the matching DataBrain handler
bad or unknown messages are printed and skipped (probably no issues once agree on payload formats)
"""

from events.messages import message_kind


class EventReceiver:
    def __init__(self, handler):
        self.routes = {
            "calibration_start": handler.on_calibration_start,
            "calibration_end": handler.on_calibration_end,
            "game_start": handler.on_game_start,
            "game_end": handler.on_game_end,
            "game_event": handler.on_game_event,
        }

    def handle(self, message):
        if not isinstance(message, dict):
            print(f"[receiver] ignored non-object message: {message!r}")
            return
        kind = message_kind(message)
        route = self.routes.get(kind)
        if route is None:
            print(f"[receiver] unknown message type {kind!r}")
            return
        print(f"[receiver] {kind}")
        try:
            route(message)
        except Exception as e:
            print(f"[receiver] error handling {kind}: {e!r}")
