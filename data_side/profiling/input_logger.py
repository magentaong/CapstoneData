"""
takes the in-game actions and reads them back for the profiler

InputLogger runs inside the Data Brain and writes each input to inputs.csv
load_inputs and summarise are used by the Profiler after the game

correct me if wrong not sure how the logging from unity to python connects
this just takes the information and suppose to combine with profiler
"""

import csv
import json

from events.messages import unwrap


class InputLogger:
    def __init__(self, get_session):
        self.get_session = get_session

    def handle(self, message):
        if not isinstance(message, dict):
            print(f"[input logger] ignored message: {message!r}")
            return
        kind, m = unwrap(message)
        if kind != "input":
            print(f"[input logger] ignored message: {message!r}")
            return
        self.record(m)

    def record(self, m):
        s = self.get_session()
        if s is None:
            return
        details = {k: v for k, v in m.items() if k not in ("t", "action")}
        s.rec.input(float(m["t"]), m.get("action", ""), json.dumps(details))


def load_inputs(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["Unix Time"] = float(r["Unix Time"])
        r["Details"] = json.loads(r["Details"]) if r["Details"] else {}
    return rows


def summarise(inputs, events):
    actions = {}
    for r in inputs:
        actions[r["Action"]] = actions.get(r["Action"], 0) + 1
    per_event = []
    for e in events:
        during = [r for r in inputs if e["start"] <= r["Unix Time"] < e["end"]]
        marked = [r["Details"]["correct"] for r in during if "correct" in r["Details"]]
        per_event.append({"event_id": e["event_id"], "inputs": len(during),
                          "accuracy": sum(marked) / len(marked) if marked else None})
    span = inputs[-1]["Unix Time"] - inputs[0]["Unix Time"] if len(inputs) > 1 else 0
    return {"total": len(inputs), "per_minute": len(inputs) / span * 60 if span else None,
            "actions": actions, "per_event": per_event}
