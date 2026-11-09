# CapstoneData

## Overview

The project is split into two repositories:

- **CapstoneGame (Unity):** Handles gameplay, calibration, game events, player inputs, and report generation.
- **CapstoneData (Python):** Handles EEG data collection, processing, real-time analysis, and post-game profiling.

Both systems communicate through WebSockets, using JSON messages to exchange information.

Currently, this repository contains the working WebSocket communication prototype under `communications/`. It allows us to send mock events from Python to Unity to test the connection without requiring actual EEG data.

## Getting Started

We can run the connection manually, or through the start script (auto-start everything for us). 

### 1. Clone the repositories

Both repositories should be cloned into the same parent directory.

```bash
git clone https://github.com/magentaong/CapstoneData.git
git clone https://github.com/FauxCrow/CapstoneGame.git
```

Your folder structure should look something like this:

```text
Something/
├── CapstoneData/
└── CapstoneGame/
```

## Manual:

### 2. Set up Python

Currently using **Python 3.12.3**, with `websockets==15.0.1` as the only external dependency.

From the `CapstoneData` directory:

**macOS / Linux**

```bash
cd CapstoneData
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

**Windows (PowerShell)**
sorry idk my powershell commands i hope it works
```powershell
cd CapstoneData
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Start the WebSocket server

Run the following from the `CapstoneData` directory.

**macOS / Linux**

```bash
.venv/bin/python -m communications.server
```

**Windows**

```powershell
.\.venv\Scripts\python.exe -m communications.server
```

By default, the server runs at:

```text
ws://127.0.0.1:8765
```

It sends 10 mock events at 1-second intervals whenever a client connects. The connection closes after the batch, but the server continues listening for new connections.

You can also configure the mock events using CLI arguments.

For example, to change the interval between events to 0.5s:

```bash
.venv/bin/python -m communications.server --interval 0.5
```

To continuously send mock events:

```bash
.venv/bin/python -m communications.server --continuous
```

To test malformed and duplicate messages:

```bash
.venv/bin/python -m communications.server --test-invalid --test-duplicate
```

To view all available options:

```bash
.venv/bin/python -m communications.server --help
```

I just realised y'all all windows ppl.. um.. change the commands to the powershell version.

Press **Ctrl+C** to stop the server.

### 4. Run the Unity project

1. Open Unity Hub and add the `CapstoneGame` project.
2. Open the project using Unity `6000.3.25f1`.
3. Navigate to `Assets/Scenes/WebSocketPrototype.unity`.
4. Make sure the Python WebSocket server is running.
5. Enter Play Mode in Unity.

Unity should connect to the Python server and receive the mock JSON events. You can check the Unity Console for incoming messages and connection logs.

Make sure the WebSocket URL configured in Unity matches the Python server's address and port.

### 5. Run the Python tests (if you want)

From `CapstoneData`:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

**Note:** Python sends mock recommendations for next event


## Auto-start both:

From `CapstoneData`:

**macOS**

```bash
.venv/bin/python scripts/start_dev.py
```

The launcher starts Python and verifies its WebSocket handshake. If the 
`CapstoneGame` project is already open, it reuses that Editor and its current scenes. It enters Play Mode if needed, or reconnects the receiver if already playing. Else it opens the project in the version from `ProjectVersion.txt` and enters `Assets/Scenes/WebSocketPrototype.unity` in Play Mode.

With no server options it uses continuous mock traffic. 

Press **Ctrl+C** to stop Python and exit Play Mode only if the launcher started it.

An Editor opened by the launcher closes only when there is no unsaved content.

To stop Python and also close Unity (including a reused Editor), run this in
another terminal from `CapstoneData`:

```bash
.venv/bin/python scripts/stop_dev.py
```

OR Stopping Play Mode in Unity or closing its Editor.

If Unity is already open, let it finish compiling before running the launcher. If it doesn’t connect, try Assets > Refresh and run it again.

Server only:

```bash
.venv/bin/python scripts/start_dev.py --server-only
```

Custom paths and server options:

```bash
.venv/bin/python scripts/start_dev.py --unity-editor "/path/to/Unity executable" --project "/path/to/CapstoneGame" -- --port 9000 --tags ENCOUNTER --continuous
```

You can just run the script with no options, but for clarity and docs sake: 

- `--server-only`: starts Python without opening or controlling Unity.
- `--project`: points to your Unity project if it isn't in the sibling `CapstoneGame` folder.
- `--unity-editor`: points to `Unity.exe` or `Unity.app` if Unity is installed somewhere else.
- `--scene`: picks the scene to open in a new Editor. The default is `Assets/Scenes/WebSocketPrototype.unity`; an already-open Editor will use its current scene
- `--`: anything after this goes to the Python server, like `-- --port 9000 --continuous`.
- `--help`: shows these options in the terminal.

With no server options, mock events run continuously. If you add server options after `--`, include ur parsing commands.

Check the Unity Console to see the mock events coming in.

# BIG NOTE!!!! to test in windows.