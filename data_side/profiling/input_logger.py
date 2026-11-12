"""
takes the in-game actions and reads them back for the profiler

InputLogger runs inside the Data Brain and writes each input to inputs.csv
load_inputs and summarise are used by the Profiler after the game

correct me if wrong not sure how the logging from unity to python connects
this just takes the information and suppose to combine with profiler
"""

import csv
import json

from common import now


class InputLogger:
    def __init__(self, get_session):
        self.get_session = get_session

    def handle(self, message):
        if not isinstance(message, dict) or message.get("type") != "input":
            print(f"[input logger] ignored message: {message!r}")
            return
        s = self.get_session()
        if s is None:
            return
        t = float(message.get("t", now()))
        details = {k: v for k, v in message.items() if k not in ("type", "t", "action")}
        s.rec.input(t, message.get("action", ""), json.dumps(details))


def load_inputs(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["Unix Time"] = float(r["Unix Time"])
        r["Details"] = json.loads(r["Details"]) if r["Details"] else {}
    return rows


def summarise(inputs, events):
    # TODO: analysis of player inputs for the profile
    pass
