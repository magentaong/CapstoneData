"""
Start the mock server and launch or reuse and already open Unity and enters play mode. 

Ctrl+C and stop_dev.py both ends the session.

FYI:
I put the child processes in separate process groups/sessions so Ctrl+C doesn't interrupt Unity directly, and allows the launcher to handle the shutdown.

From what I understand, Ctrl+C might otherwise interrupt everything at once, so this lets the launcher handle stopping them instead. (this mostly a safeguard)

Apparently Windows also needs this for how the server gets stopped. Not too familiar with the process group stuff for windows tbh, but ig no harm keeping this? e
"""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

DATA_ROOT = Path(__file__).resolve().parents[1]
UNITY_STARTUP_TIMEOUT = 180  # unity 3 mins to start up + enter playmode, might need to adjust in the future 


def parse_args(argv=None):
    # ref: https://docs.python.org/3.12/howto/argparse.html 
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-only", action="store_true", help="Only start Python; leave Unity alone")
    parser.add_argument("--project", type=Path, default=DATA_ROOT.parent / "CapstoneGame",
                        help="Unity project folder (default: CapstoneGame folder in the same level)")
    parser.add_argument("--unity-editor", type=Path,
                        help="add ur path after --unity-editor to set the correct path")
    parser.add_argument("--scene", default="Assets/Scenes/WebSocketPrototype.unity",
                        help="Scene to open in a new Editor (default: WebSocketPrototype)")
    parser.add_argument("server_args", nargs=argparse.REMAINDER,
                        help="Put Python server options after --, e.g. -- --port 9000 --continuous")
    args = parser.parse_args(argv)
    if args.server_args[:1] == ["--"]:
        args.server_args = args.server_args[1:]
    return args


def find_unity(project, configured=None):
    """Use the supplied path, or find this project's Unity version in the Hub folder."""
    # ref i used https://gist.github.com/platinio/2ca6b2572526bf14db353babbabce950 for `detect_unity_version` and `find_unity`
    # oso ref unity docs here https://docs.unity.com/en-us/engine/6000.3/manual/unity-editor/command-line-arguments/editor for launching the Editor and the usual executable paths.
    # sorry dumping it here in case smth breaks and we need debug.
    if configured:
        executable = Path(configured).expanduser()
    else:
        # Unity puts its version on the first line, e.g. m_EditorVersion: 6000.3.25f1.
        version_file = project / "ProjectSettings/ProjectVersion.txt"
        version = version_file.read_text().splitlines()[0].split(":", 1)[1].strip()
        if sys.platform == "darwin":
            executable = Path("/Applications/Unity/Hub/Editor") / version / "Unity.app/Contents/MacOS/Unity"
        elif os.name == "nt":

            # this script here might fail, ref docs and google but if it does please help fix.
            # or you can also ignore this and just run the server and unity sep... :(
            hub = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Unity/Hub/Editor"
            executable = hub / version / "Editor/Unity.exe"
        else:
            raise ValueError("Use --unity-editor followed by ur full path to Unity to set it.")
    if executable.suffix == ".app":
        executable /= "Contents/MacOS/Unity"
    return executable.resolve()


def existing_editor(project):
    # If Unity updated this recently, then the project's Editor is still open, so we'll use the existing editor
    info = read_json(project / "Temp/MagesDev/editor.json")
    if info and time.time() * 1000 - info["timestamp_ms"] < 10000:
        if info["active"]:
            raise RuntimeError("Another start_dev.py is running, can't start a new session.")
        return info
    if (project / "Temp/UnityLockfile").exists():
        raise ValueError("Unity is locked, save ur current unity work then rerun the command")
    return None


def request_editor_reuse(project, session, editor):
    requests = project / "Temp/MagesDev/requests"
    requests.mkdir(parents=True, exist_ok=True)
    pending = requests / (session.name + ".tmp")
    pending.write_text(json.dumps({"directory": str(session), "token": editor["token"]}))
    pending.replace(pending.with_suffix(".json"))


# Needed for CTRL_BREAK_EVENT on Windows, if i'm not wrong
# ref: https://docs.python.org/3.12/library/subprocess.html
def child_options():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def wait_for_server(server, port):
    from websockets.sync.client import connect
    from websockets.exceptions import WebSocketException
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Python couldn't start. Check the server output above.")
        try:
            # Wait for Python to accept connections before starting Unity
            with connect(f"ws://127.0.0.1:{port}", proxy=None, open_timeout=0.3, close_timeout=0.3):
                return
        except (OSError, TimeoutError, WebSocketException):
            time.sleep(0.1)
    raise RuntimeError("Python WebSocket server did not become ready")


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        # Unity may still be writing the status file. Read it on the next loop.
        return {}


def write_launcher_status(session, state):
    pending = session / "launcher-status.tmp"
    pending.write_text(json.dumps({"state": state, "timestamp_ms": time.time() * 1000}))
    pending.replace(session / "launcher-status.json")


def stop_unity(unity, session):
    if unity is not None and unity.poll() is not None:
        return
    (session / "stop").touch()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if unity is not None and unity.poll() is not None:
            return
        status = read_json(session / "status.json")
        if status.get("state") in ("stopped", "left_open", "error"):
            print(status["message"], flush=True)
            return
        time.sleep(0.1)
    print("Unity hasn't confirmed it stopped, check the Editor.", flush=True)


def stop_server(server):
    if server.poll() is not None:
        return
    server.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # if python hasn't stopped for 5s, we terminate
        server.terminate()
        server.wait(timeout=5)


def main(argv=None):
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    args = parse_args(argv)
    server = unity = session = registry = None
    requested = False
    unity_finished = False
    try:
        sys.path.insert(0, str(DATA_ROOT))
        from communications.server import parse_args as server_args

        options = args.server_args or ["--continuous"]
        config = server_args(options)
        project = args.project.expanduser().resolve()
        if not args.server_only:
            editor = existing_editor(project)
            if editor is None:
                executable = find_unity(project, args.unity_editor)
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", config.port))
            except OSError:
                raise RuntimeError(f"Port {config.port} is in use. Stop the existing server first.")

        # Start Python first, then register this session so stop_dev.py can find it.
        server = subprocess.Popen([sys.executable, "-m", "communications.server", *options],
                                  cwd=DATA_ROOT, **child_options())
        wait_for_server(server, config.port)
        print(f"Python ready at ws://127.0.0.1:{config.port}", flush=True)

        session = Path(tempfile.mkdtemp(prefix="mages-dev-"))
        (session / "session.json").write_text(json.dumps({
            "project": str(project), "scene": Path(args.scene).as_posix(),
            "serverUrl": f"ws://127.0.0.1:{config.port}", "server_only": args.server_only,
        }))
        write_launcher_status(session, "running")
        registry = DATA_ROOT / "tmp/dev-sessions" / (session.name + ".json")
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"project": str(project), "directory": str(session)}))

        if not args.server_only:
            if editor is not None:
                print(f"Reusing open Unity Editor (PID {editor.get('pid')}); keeping its current scenes.\nSession: {session}", flush=True)
                request_editor_reuse(project, session, editor)
            else:
                command = [str(executable), "-projectPath", str(project),
                           "-executeMethod", "Capstone.Editor.DevSession.Start",
                           "-magesDevSession", str(session), "-logFile", str(session / "unity.log")]
                print(f"Starting Unity: {project}\nSession and log: {session}", flush=True)
                unity = subprocess.Popen(command, **child_options())
            requested = True
        else:
            print("Server-only session running. Press Ctrl+C to stop.", flush=True)

        # One loop to handle the startup, Unity's Stop button, and stop_dev.py requests
        playing = args.server_only
        deadline = time.monotonic() + UNITY_STARTUP_TIMEOUT
        while server.poll() is None:
            write_launcher_status(session, "running")
            if (session / "stop").exists():
                break
            status = read_json(session / "status.json")
            if status.get("state") == "stopped" or (unity is not None and unity.poll() is not None):
                unity_finished = True
                print("Unity stopped; stopping Python.", flush=True)
                break
            if status.get("state") == "error":
                raise RuntimeError(status["message"])
            if not playing:
                if status.get("state") == "playing":
                    print("Unity entered Play Mode. Press Ctrl+C to stop.", flush=True)
                    playing = True
                elif time.monotonic() >= deadline:
                    raise RuntimeError(f"Unity didn't enter Play Mode. Check {session / 'unity.log'}.")
            time.sleep(0.2)
        if server.returncode not in (None, 0):
            raise RuntimeError(f"Python stopped with code {server.returncode}.")
        if unity is not None and unity.returncode not in (None, 0):
            raise RuntimeError(f"Unity stopped with code {unity.returncode}.")
    except KeyboardInterrupt:
        print("\nStopping development session…", flush=True)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        # Python stops before Unity, so if Unity sends a message during the shutdown, there's a chance that it's gone 
        # shouldn't be an issue in the future
        if server is not None:
            stop_server(server)
        if requested and not unity_finished:
            stop_unity(unity, session)
        if session is not None:
            write_launcher_status(session, "stopped")
        if registry is not None:
            registry.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
