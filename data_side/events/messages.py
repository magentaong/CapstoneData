
"""
crafts the messages exchanged from data side with game both directions
"""
import uuid
from dataclasses import dataclass, asdict
from typing import Optional

from common import now

STRESS_TYPES = ("TIME", "ANTICIPATION", "SITUATIONAL", "ENCOUNTER")
#same as StressTag in the game (StressEvent.cs), each should mostly(?) link to one of the competencies
INTENSITY_MIN, INTENSITY_MAX = 1, 5
#forgot the scale 1-5 or 1-10
ENVELOPE_FIELDS = ("version", "message_id", "type", "timestamp_ms", "payload")
#unity wraps every message in these, the rest is in payload
CONTROL_TYPES = ("calibration_start", "calibration_end", "game_start", "game_end")


@dataclass
class GameEvent:
    event_id: int
    stress_type: str
    start: float
    end: float
    received: float
    level: Optional[int] = None
    score: Optional[float] = None
    result: Optional[dict] = None
    sent: Optional[dict] = None

    def to_dict(self):
        return asdict(self)


def unwrap(message):
    kind = str(message.get("type", "")).lower()
    m = {k: v for k, v in message.items() if k not in ENVELOPE_FIELDS}
    if isinstance(message.get("payload"), dict):
        m.update(message["payload"])
    if "timestamp_ms" in message:
        m["t"] = message["timestamp_ms"] / 1000
    m.setdefault("t", now())
    return kind, m


def parse_game_event(started, ended, event_id, received):
    return GameEvent(event_id, started["event_tag"], float(started["t"]), float(ended["t"]), received,
                     started.get("intensity"))


def stress_message(event_tag, intensity):
    if event_tag not in STRESS_TYPES:
        raise ValueError(f"event_tag must be one of {STRESS_TYPES}, got {event_tag!r}")
    if isinstance(intensity, bool):
        raise ValueError(f"intensity must be a number, got {intensity!r}")
    intensity = int(round(intensity))
    if not INTENSITY_MIN <= intensity <= INTENSITY_MAX:
        raise ValueError(f"intensity must be {INTENSITY_MIN}-{INTENSITY_MAX}, got {intensity}")
    return {"event_tag": event_tag, "intensity": intensity}


def recommendation(payload, sequence):
    return {"version": 1, "message_id": f"evt-{uuid.uuid4().hex}", "sequence": sequence,
            "type": "EVENT_RECOMMENDATION", "timestamp_ms": int(now() * 1000), "payload": dict(payload)}
