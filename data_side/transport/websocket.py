
"""
Link between the Data Brain and Unity over WebSocket (ws://127.0.0.1:8765).

Please confirm if like this, hopefully understanding correctly now
"""

import asyncio
import json
import threading

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from common import HOST, GAME_WS_PORT


class WebSocketGameTransport:
    def __init__(self, on_game_message, on_input_message, host=HOST, port=GAME_WS_PORT):
        self.on_game_message = on_game_message
        self.on_input_message = on_input_message
        self.host, self.port = host, port
        self.clients = set()
        self.loop = None
        self.stopped = None

    def start(self):
        ready = threading.Event()
        threading.Thread(target=self._run, args=(ready,), daemon=True).start()
        ready.wait(5)

    def stop(self):
        if self.loop and self.stopped:
            self.loop.call_soon_threadsafe(self.stopped.set)

    def send(self, payload):
        if not self.clients:
            raise ConnectionError("no game connected")
        data = json.dumps(payload)
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self.loop).result(timeout=2)

    async def _broadcast(self, data):
        for ws in list(self.clients):
            try:
                await ws.send(data)
            except ConnectionClosed:
                self.clients.discard(ws)

    async def _handle(self, ws):
        self.clients.add(ws)
        print(f"[websocket] game connected {ws.remote_address}")
        try:
            async for raw in ws:
                try:
                    m = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    print(f"[websocket] dropped malformed message: {raw!r}")
                    continue
                handle = self.on_input_message if isinstance(m, dict) and m.get("type") == "input" else self.on_game_message
                try:
                    await asyncio.to_thread(handle, m)
                except Exception as e:
                    print(f"[websocket] error handling message: {e!r}")
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)
            print(f"[websocket] game disconnected {ws.remote_address}")

    def _run(self, ready):
        asyncio.run(self._serve(ready))

    async def _serve(self, ready):
        self.loop = asyncio.get_running_loop()
        self.stopped = asyncio.Event()
        try:
            async with serve(self._handle, self.host, self.port):
                print(f"[websocket] listening on ws://{self.host}:{self.port}")
                ready.set()
                await self.stopped.wait()
        except OSError as e:
            print(f"[websocket] cannot start on port {self.port}: {e!r}")
            ready.set()
