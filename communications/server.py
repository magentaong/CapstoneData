"""Local mock server, run `python -m communications.server --help` for configuration."""

import argparse
import asyncio
import json
import logging
import math
import signal
from functools import partial

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .mock_events import DEFAULT_TAGS, generate_events, serialize_event

LOG = logging.getLogger("mock-events")


async def send_events(connection, *, events, interval=1.0, count=10,
                      test_invalid=False, test_duplicate=False):
    """Send an iterable of events, count=None streams until disconnect/shutdown (it's unlimited)"""
    
    LOG.info("Connected: %s", connection.remote_address)
    sent = 0

    try:
        if test_invalid:
            await connection.send('{"broken":')
            LOG.info("Sent malformed JSON test frame")

        for event in events:
            if connection.state.name != "OPEN":
                break

            message = serialize_event(event)
            await connection.send(message)
            sent += 1
            LOG.info("Sent id=%s sequence=%s", event["message_id"], event["sequence"])

            if test_duplicate and sent == 1:
                await connection.send(message)
                LOG.info("Repeated id=%s (duplicate test)", event["message_id"])

            if count is not None and sent >= count:
                await connection.close(code=1000, reason="Mock batch complete")
                break

            try:
                # wait between the mock events, but then close it if Unity disconnects.
                await asyncio.wait_for(connection.wait_closed(), timeout=interval)
                break
            except TimeoutError:
                pass

    except ConnectionClosed as error:
        LOG.info("Client disconnected: %s", error)

    finally:
        LOG.info("Connection finished: %s; sent=%d", connection.remote_address, sent)


async def receive_messages(connection):
    try:
        async for frame in connection:
            try:
                message = json.loads(frame)
                if not isinstance(message, dict):
                    raise ValueError("expected a JSON object")
            except (ValueError, TypeError) as error:
                LOG.warning("Ignored Unity message: %s", error)
                continue
            LOG.info("Received from Unity: %s", message)
    except ConnectionClosed:
        pass


async def handle_connection(connection, args):
    # Listen on the same connection while the mock recommendations are constantly being sent.
    await asyncio.gather(receive_messages(connection), send_events(
        connection,
        events=generate_events(args.tags, args.intensity),
        interval=args.interval,
        count=None if args.continuous else args.count, # None means send until disconnect
        test_invalid=args.test_invalid,
        test_duplicate=args.test_duplicate,
    ))


def parse_args(argv=None):
    """
    Configure mock traffic
    Use --test-invalid to send one malformed message.
    Add --test-duplicate to also repeat the first valid message.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)

    # i'm realising that we don't really need by interval anymore, since events will be sent when there is one to be sent
    # TODO: recouncile with newer design and either remove this arg/parameter, or modify it to fit new use case, 
    # for now, i'm leaning towards keeping it here cause I think it's needed for mock server/mock testing
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between events") 

    parser.add_argument("--count", type=int, default=10, help="Events per web socket connection")
    parser.add_argument("--continuous", action="store_true", help="Ignore --count")
    parser.add_argument("--tags", nargs="+", default=list(DEFAULT_TAGS), help="Cycle through these tags")
    parser.add_argument("--intensity", nargs="+", type=int, default=[3], help="Cycle through integers from 1 to 5")
    parser.add_argument("--test-invalid", action="store_true", help="Send one malformed frame first")
    parser.add_argument("--test-duplicate", action="store_true", help="Repeat the first valid frame once")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be a finite positive number")
    if args.count <= 0:
        parser.error("--count must be positive (use --continuous for an unlimited stream)")
    try:
        next(generate_events(args.tags, args.intensity))
    except ValueError as error:
        parser.error(str(error))
    return args


# the main server logic is here
async def run(args):
    """Run the WebSocket server until interrupted (ctrl-c)"""
    async with serve( partial(handle_connection, args=args),"127.0.0.1", args.port):
        LOG.info("WebSocket server running on port %d", args.port)
        await asyncio.Event().wait()


def main():
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        LOG.info("Server stopped")
    except OSError as error:
        LOG.error("Cannot start server: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
