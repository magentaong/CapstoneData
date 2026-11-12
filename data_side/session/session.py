
"""
stores the IDs, time marks, game events, calibration profile, session folder and its Recorder

created by the SessionManager.
"""

import os
import time

from common import OUTPUT_DIR
from session.recorder import Recorder


class Session:
    def __init__(self, session_id=None, player_id=None, source="game"):
        self.session_id = session_id or time.strftime("session_%Y%m%d_%H%M%S")
        self.player_id = player_id
        self.source = source
        self.marks = {}
        self.events = []
        self.markers = []
        self.calibration = None
        self.folder = os.path.abspath(os.path.join(OUTPUT_DIR, self.session_id))
        self.rec = Recorder(self.folder)
        self.workers = []
        self.finished = False
