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

**Note:** The current prototype here only handles Python-to-Unity mock event communication.


## Auto-start both: