"""
Shared config + tiny UDP/JSON messaging helpers.

Every message is a JSON dict.
time.time() (Unix seconds) is a shared clock.

C# bridge uses clock: DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.
"""
import json
import os
import socket
import time

HOST = "127.0.0.1"

PORT_EEG_IN = 5001       # EEG bridge -> Data Brain
PORT_BRAIN_IN = 5002     # Game -> Data Brain
PORT_GAME_IN = 5003      # Data Brain -> Game
PORT_LOGGER_IN = 5004    # Game -> Input Logger
PORT_BRIDGE_CMD = 5005   # Data Brain -> EEG bridge
PORT_PROFILER_IN = 5006  # Data Brain + Input Logger -> Profiler 
# TODO: GAME_WS_PORT = 8765 (Unity <-> Data Brain WebSocket) replaces 5002 / 5003

# EEG variables
FS = 250                                  # Hz
CHANNELS = ["fp1", "fp2", "t3", "t4"]     # need to check which channel is which reading
UV_PER_UNIT = 0.61                        # raw unit -> microvolts
MAINS_HZ = 50
EEG_LAYOUT = "channel_major"              # "channel_major" or "interleaved"

# Analysis windows (sec)
PRE_EVENT_S = 1.0        # look from 1 sec before the event timestamp to include moment event occurs
POST_EVENT_S = 5.0       # look for any residual lingering (? to confirm)
LIVE_UPDATE_S = 1.0      # default interval for the recording
STREAM_TIMEOUT_S = 10.0   # no EEG for this long then stream is considered down

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
MAX_UDP = 60000          # keep messages under UDP limit


def now() -> float:
    return time.time()


class Sender:
    def __init__(self, port: int, host: str = HOST):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, msg: dict, stamp: bool = True) -> None:
        if stamp:
            msg.setdefault("t", now())
        data = json.dumps(msg, default=float).encode()
        if len(data) > MAX_UDP:
            raise ValueError(f"message too large for UDP ({len(data)} bytes)")
        self.sock.sendto(data, self.addr)


class Receiver:

    def __init__(self, port: int, host: str = HOST, timeout: float = 0.5):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.settimeout(timeout)

    def recv_from(self):
        try:
            data, addr = self.sock.recvfrom(65536)
        except socket.timeout:
            return None, None
        try:
            return json.loads(data.decode()), addr
        except (UnicodeDecodeError, json.JSONDecodeError):
            print(f"[net] dropped malformed message from {addr}")
            return None, None

    def recv(self):
        return self.recv_from()[0]

    def reply(self, addr, msg: dict) -> None:
        msg.setdefault("t", now())
        self.sock.sendto(json.dumps(msg, default=float).encode(), addr)