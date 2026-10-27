"""
Mocking events to test the integration with websocket from python -> unity
TODO in the future: Potentially mock the entire flow, currently pending on folder structure/ functions input & output for data processing.
"""

import json
import time
import uuid
from itertools import count

DEFAULT_TAGS = ("TIME", "ANTICIPATION", "SITUATIONAL", "ENCOUNTER")


def generate_events(tags=DEFAULT_TAGS, intensity=(3,)):

    if not tags or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise ValueError("tags must contain non-empty strings")
        
    if not intensity or any(type(value) is not int or not 1 <= value <= 5
                             for value in intensity):
        raise ValueError("intensity must contain integers from 1 to 5")
    
    session_id = uuid.uuid4().hex

    # For clarity: timestamp here refers to the time the message was generated, added it to potentially check for latency in the future (if need/as a just in-case)
    for sequence in count(1):
        yield {
            "version": 1,
            "message_id": f"evt-{session_id}-{sequence:03d}",
            "sequence": sequence,
            "type": "EVENT_RECOMMENDATION",
            "timestamp_ms": time.time_ns() // 1_000_000,
            "payload": {
                "event_tag": tags[(sequence - 1) % len(tags)],
                "intensity": intensity[(sequence - 1) % len(intensity)],
            },
        }


def serialize_event(event):
    return json.dumps(event, separators=(",", ":"), allow_nan=False)
