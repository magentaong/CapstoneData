
"""
crafts the messages exchanged from data side with game both directions
"""
from dataclasses import dataclass, asdict
from typing import Optional

STRESS_TYPES = ("time", "information", "comms", "decision", "resilience", "attention")
#can change this ^ to the different events but each event should mostly(?) link to one of the competencies
INTENSITY_MIN, INTENSITY_MAX = 1, 5
#forgot the scale 1-5 or 1-10
GAME_EVENT_FIELDS = {"stress_type", "start_time", "end_time"}
#format receiving from the game to analyse
CONTROL_TYPES = ("calibration_start", "calibration_end", "game_start", "game_end")


@dataclass
class GameEvent:
    event_id: int
    stress_type: str
    start: float
    end: float
    received: float
    result: Optional[dict] = None

    def to_dict(self):
        return asdict(self)


def message_kind(message):
    kind = message.get("type")
    if kind is None and GAME_EVENT_FIELDS <= message.keys():
        return "game_event"
    return kind


def parse_game_event(message, event_id, received):
    return GameEvent(event_id, message["stress_type"], float(message["start_time"]),
                     float(message["end_time"]), received)


def stress_message(event_tag, intensity):
    if event_tag not in STRESS_TYPES:
        raise ValueError(f"event_tag must be one of {STRESS_TYPES}, got {event_tag!r}")
    if isinstance(intensity, bool):
        raise ValueError(f"intensity must be a number, got {intensity!r}")
    intensity = int(round(intensity))
    if not INTENSITY_MIN <= intensity <= INTENSITY_MAX:
        raise ValueError(f"intensity must be {INTENSITY_MIN}-{INTENSITY_MAX}, got {intensity}")
    return {"event_tag": event_tag, "intensity": intensity}
