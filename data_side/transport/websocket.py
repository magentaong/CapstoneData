
"""Compatibility import for Data Brain's shared WebSocket transport."""

import sys
from pathlib import Path

# Let data_brain.py import communications from the parent CapstoneData folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from communications.server import WebSocketGameTransport