"""
Stop this project's start_dev.py sessions and request a Unity Editor exit.
"""

import argparse
import json
from pathlib import Path
import sys
import time

DATA_ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def active_sessions(project):
    """
    Check sessions started by start_dev.py, and check last udpate timestamp here cause an old session file might be treated as active sessions.
    """
    sessions = []

    for entry in (DATA_ROOT / "tmp/dev-sessions").glob("*.json"):
        info = read_json(entry)

        if info.get("project") != str(project) or not isinstance(info.get("directory"), str):
            continue

        session = Path(info["directory"])

        if read_json(session / "session.json").get("project") != str(project):
            continue

        state = read_json(session / "launcher-status.json")

        if state.get("state") == "stopped":
            continue
        stamp = state.get("timestamp_ms", 0)

        if not isinstance(stamp, (int, float)) or not 0 <= time.time() * 1000 - stamp <= 10000:
            print(f"Ignoring an unresponsive launcher record: {session}. Its processes were left alone.", file=sys.stderr)
            continue
        sessions.append(session)
    return sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DATA_ROOT.parent / "CapstoneGame")
    parser.add_argument("--timeout", type=float, default=35)
    args = parser.parse_args(argv)

    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be finite and positive")
    try:
        sessions = active_sessions(args.project.expanduser().resolve())
        if not sessions:
            print("No active start_dev.py sessions for this project.")
            return 0
        for session in sessions:
            # .touch() to leave a request to leave a request for Unity helper and launcher to handle
            (session / "close-editor").touch()
            (session / "stop").touch()
        print("Stopping Python and requesting Unity to close safely…", flush=True)

        deadline = time.monotonic() + args.timeout

        while any(read_json(session / "launcher-status.json").get("state") != "stopped" for session in sessions):

            if time.monotonic() >= deadline:
                raise RuntimeError("Shutdown was not confirmed in time, check ur Unity in case")
            time.sleep(0.1)

        incomplete = False

        for session in sessions:

            if read_json(session / "session.json").get("server_only"):
                continue

            status = read_json(session / "status.json")

            if not status.get("editor_closed"):
                print("Python stopped, Unity: " + status.get("message", "Editor exit was not confirmed"))
                incomplete = True

        if incomplete:
            print("Save any unsaved work and close Unity manually.")
            return 1
        
        print("Session stopped.")
        return 0
    
    except (OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
