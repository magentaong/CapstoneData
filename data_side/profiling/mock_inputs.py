"""
fake player inputs for testing, until unity sends INPUT messages
started by data_brain.py --mock-inputs, every input is marked "mock": true

TODO: remove once unity sends INPUT messages
"""

import random
import threading
import time

from common import now

ACTIONS = ("move", "click", "interact")
WRONG_CALM, WRONG_EVENT = 0.1, 0.4


class MockInputs:
    def __init__(self, get_session, in_event, record):
        self.get_session = get_session
        self.in_event = in_event
        self.record = record
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            time.sleep(random.uniform(0.4, 1.5))
            s = self.get_session()
            if s is None or "game_start" not in s.marks:
                continue
            wrong = WRONG_EVENT if self.in_event() else WRONG_CALM
            self.record({"t": now(), "action": random.choice(ACTIONS),
                         "correct": random.random() > wrong, "mock": True})
