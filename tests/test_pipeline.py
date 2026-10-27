import asyncio
import contextlib
import io
import json
import time
import unittest
from functools import partial
from itertools import islice

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from communications.mock_events import generate_events, serialize_event
from communications.server import parse_args, send_events


class GenerationTests(unittest.TestCase):
    def test_contract_and_serialization(self):
        before = time.time_ns() // 1_000_000
        events = list(islice(generate_events(), 10))
        after = time.time_ns() // 1_000_000
        self.assertEqual([e["sequence"] for e in events], list(range(1, 11)))
        self.assertEqual(len({e["message_id"] for e in events}), 10)
        tags = ["TIME", "ANTICIPATION", "SITUATIONAL", "ENCOUNTER"]
        for index, event in enumerate(events):
            self.assertEqual(json.loads(serialize_event(event)), event)
            self.assertEqual(event["version"], 1)
            self.assertEqual(event["type"], "EVENT_RECOMMENDATION")
            self.assertEqual(event["payload"], {"event_tag": tags[index % len(tags)], "intensity": 3})
            self.assertTrue(before <= event["timestamp_ms"] <= after)

    def test_new_connection_ids_and_configuration(self):
        first = list(islice(generate_events(["TIME", "ENCOUNTER"], [1, 4]), 3))
        second = next(generate_events())
        self.assertNotEqual(first[0]["message_id"], second["message_id"])
        self.assertEqual(second["sequence"], 1)
        self.assertEqual([e["payload"]["event_tag"] for e in first], ["TIME", "ENCOUNTER", "TIME"])
        self.assertEqual([e["payload"]["intensity"] for e in first], [1, 4, 1])

    def test_cli_defaults_match_generator(self):
        args = parse_args([])
        self.assertEqual(args.tags, ["TIME", "ANTICIPATION", "SITUATIONAL", "ENCOUNTER"])
        self.assertEqual(args.intensity, [3])
        configured = list(islice(generate_events(args.tags, args.intensity), 8))
        defaults = list(islice(generate_events(), 8))
        self.assertEqual([e["payload"] for e in configured], [e["payload"] for e in defaults])

    def test_intensity_range_type_and_independent_cycles(self):
        args = parse_args(["--tags", "TIME", "ENCOUNTER", "--intensity", "1", "2", "3", "4", "5"])
        events = list(islice(generate_events(args.tags, args.intensity), 10))
        self.assertEqual([e["payload"]["event_tag"] for e in events], ["TIME", "ENCOUNTER"] * 5)
        self.assertEqual([e["payload"]["intensity"] for e in events], [1, 2, 3, 4, 5] * 2)
        self.assertTrue(all(type(e["payload"]["intensity"]) is int for e in events))
        for values in ((), (0,), (-1,), (6,), (True,), (1.5,), ("3",)):
            with self.subTest(intensity=values), self.assertRaises(ValueError):
                next(generate_events(intensity=values))

    def test_deployer_tags_remain_available(self):
        args = parse_args(["--tags", "AUDIO", "OBJECT", "SHADER", "--intensity", "1", "5"])
        events = list(islice(generate_events(args.tags, args.intensity), 6))
        self.assertEqual([e["payload"]["event_tag"] for e in events], ["AUDIO", "OBJECT", "SHADER"] * 2)
        self.assertEqual([e["payload"]["intensity"] for e in events], [1, 5] * 3)

    def test_invalid_configuration(self):
        for args in (["--interval", "0"], ["--interval", "nan"], ["--interval", "inf"],
                     ["--count", "0"], ["--port", "65536"], ["--tags", " "],
                     ["--intensity", "0"], ["--intensity", "6"], ["--intensity", "2147483648"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_args(args)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def receive_batch(self, **options):
        handler = partial(send_events, events=generate_events(), interval=0.001, **options)
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}", proxy=None) as client:
                frames = await asyncio.wait_for(self.collect(client), timeout=5)
                self.assertEqual(client.close_code, 1000)
                return frames

    @staticmethod
    async def collect(client):
        return [message async for message in client]

    async def test_ten_events_and_clean_close(self):
        frames = await self.receive_batch()
        self.assertEqual(len(frames), 10)
        self.assertEqual([json.loads(f)["sequence"] for f in frames], list(range(1, 11)))

    async def test_fault_injection_preserves_ten_valid_events(self):
        frames = await self.receive_batch(test_invalid=True, test_duplicate=True)
        self.assertEqual(len(frames), 12)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(frames[0])
        valid = [json.loads(frame) for frame in frames[1:]]
        self.assertEqual(valid[0], valid[1])
        self.assertEqual(len({e["message_id"] for e in valid}), 10)

    async def test_inbound_malformed_json_does_not_interrupt_batch(self):
        # The prototype sends only; client application messages aren't parsed.
        handler = partial(send_events, events=generate_events(), count=3, interval=0.01)
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}", proxy=None) as client:
                await client.send('{"broken":')
                frames = await asyncio.wait_for(self.collect(client), timeout=5)
                self.assertEqual([json.loads(f)["sequence"] for f in frames], [1, 2, 3])
                self.assertEqual(client.close_code, 1000)

    async def test_disconnect_interrupts_long_interval(self):
        done = asyncio.Event()

        async def handler(connection):
            try:
                await send_events(connection, events=generate_events(), count=None, interval=3600)
            finally:
                done.set()

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}", proxy=None) as client:
                await asyncio.wait_for(client.recv(), 2)
            await asyncio.wait_for(done.wait(), 2)

    async def test_continuous_exceeds_ten(self):
        handler = partial(send_events, events=generate_events(), count=None, interval=0.001)
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}", proxy=None) as client:
                for sequence in range(1, 13):
                    event = json.loads(await asyncio.wait_for(client.recv(), 2))
                    self.assertEqual(event["sequence"], sequence)

    async def test_cancellation_propagates(self):
        sending = asyncio.get_running_loop().create_future()

        async def handler(connection):
            task = asyncio.create_task(send_events(
                connection, events=generate_events(), count=None, interval=3600))
            sending.set_result(task)
            try:
                await task
            finally:
                await connection.close()

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}", proxy=None) as client:
                await asyncio.wait_for(client.recv(), 2)
                task = await asyncio.wait_for(sending, 2)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)


if __name__ == "__main__":
    unittest.main()
