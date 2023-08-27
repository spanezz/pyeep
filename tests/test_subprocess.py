from __future__ import annotations

import asyncio
import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path

from pyeep.component.subprocess import TopComponent
from pyeep.messages.component import DeviceScanRequest, Shutdown
from pyeep.messages.message import Message


class MockHub:
    def __init__(self):
        self.messages_sent: list[Message] = []

    def _running_in_hub(self):
        return True

    def send(self, msg: Message):
        self.messages_sent.append(msg)


class TestSubprocess(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.workdir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    async def test_start_stop(self):
        scriptfile = self.workdir / "script"
        scriptfile.write_text("#!/bin/sh\nsleep 100")
        scriptfile.chmod(0o755)

        class Comp(TopComponent):
            def get_commandline(self):
                return [scriptfile]

        comp = Comp(hub=MockHub())
        comp_task = asyncio.create_task(comp.run())

        while comp.proc is None:
            await asyncio.sleep(0.1)
        pid = comp.proc.pid

        comp.receive(Shutdown())

        await comp_task

        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    async def test_send(self):
        outfile = self.workdir / "output"

        scriptfile = self.workdir / "script"
        scriptfile.write_text(f"#!/bin/sh\nnc -U $1 > {outfile}")
        scriptfile.chmod(0o755)

        class Comp(TopComponent):
            def get_commandline(self):
                return [scriptfile, self.workdir / "socket"]

        comp = Comp(hub=MockHub())
        comp_task = asyncio.create_task(comp.run())

        while comp.proc is None:
            await asyncio.sleep(0.1)

        comp.receive(DeviceScanRequest(duration=3.14, ts=12.34))

        comp.receive(Shutdown())

        await comp_task

        output = outfile.read_text()
        self.assertNotEqual(output, "")
        parsed = json.loads(output)
        self.assertEqual(parsed, {
            '__class__': 'DeviceScanRequest',
            '__module__': 'pyeep.messages.component',
            'dst': None,
            'duration': 3.14,
            'name': 'devicescanrequest',
            'src': None,
            'ts': 12.34})

    async def test_receive(self):
        payload = {
            '__class__': 'DeviceScanRequest',
            '__module__': 'pyeep.messages.component',
            'dst': None,
            'duration': 3.14,
            'name': 'devicescanrequest',
            'src': None,
            'ts': 12.34,
        }
        encoded = shlex.quote(json.dumps(payload))

        outfile = self.workdir / "output"

        scriptfile = self.workdir / "script"
        scriptfile.write_text(f"#!/bin/sh\necho {encoded} | nc -U $1 > {outfile}")
        scriptfile.chmod(0o755)

        class Comp(TopComponent):
            def get_commandline(self):
                return [scriptfile, self.workdir / "socket"]

        hub = MockHub()
        comp = Comp(hub=hub)
        comp_task = asyncio.create_task(comp.run())

        while comp.proc is None:
            await asyncio.sleep(0.1)

        comp.receive(Shutdown())

        await comp_task

        self.assertEqual(len(hub.messages_sent), 1)
        msg = hub.messages_sent[0]
        self.assertIsInstance(msg, DeviceScanRequest)
        self.assertEqual(msg.duration, 3.14)
        self.assertEqual(msg.ts, 12.34)

        self.assertEqual(outfile.read_text(), "")
