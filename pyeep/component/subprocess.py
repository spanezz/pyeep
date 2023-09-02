from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from ..messages.component import Shutdown
from ..messages.jsonable import Jsonable
from .aio import AIOComponent

if TYPE_CHECKING:
    from ..messages.message import Message


# See https://bugs.python.org/issue43884
# It looks like asyncio is currently not very good at doing subprocess pipes
# reading from stdout, and a Unix Domain Socket is a working and more stable
# replacement


class SubprocessComponent(AIOComponent):
    """
    Common functionality for the top and bottom end of a subprocess component
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.read_messages_task: asyncio.Task | None = None

    async def _read_messages(self):
        """
        Task used to read messages from the remote endpoint
        """
        try:
            while (line := await self.reader.readline()):
                jsonable = json.loads(line)
                cls = Jsonable.jsonable_class(jsonable)
                if cls is None:
                    continue

                jsonable["src"] = self

                try:
                    msg = cls(**jsonable)
                except Exception as e:
                    self.logger.error("cannot instantiate message: %s", e)
                    continue

                await self.process_remote_message(msg)
        finally:
            self.receive(Shutdown())

    async def forward_message(self, msg: Message):
        """
        Forward a message to the remote endpoint
        """
        line = json.dumps(msg.as_jsonable()) + "\n"
        self.writer.write(line.encode())
        await self.writer.drain()

    async def main_loop(self):
        while True:
            match (msg := await self.next_message()):
                case Shutdown():
                    break
                case _:
                    await self.process_local_message(msg)

    async def process_local_message(self, msg: Message):
        """
        Process a message received from the local hub
        """
        # if msg.src != self and self.writer is not None:
        #     await self.forward_message(msg)
        pass

    async def process_remote_message(self, msg: Message):
        """
        Process a message received from the remote endpoint
        """
        # self.send(msg)
        pass


class TopComponent(SubprocessComponent):
    """
    Component that manages a child process

    This is the controller side of a BottomComponent
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.proc: asyncio.subprocess.Process | None = None
        self.returncode: int | None = None
        self.workdir: Path | None = None
        self.server: asyncio.Server | None = None

    def get_commandline(self) -> Sequence[str]:
        raise NotImplementedError(f"{self.__class__.__name__}.get_commandline not implemented")

    async def _killer(self):
        attempt = 0
        while self.proc.returncode is None:
            if attempt < 10:
                self.proc.terminate()
            else:
                self.proc.kill()
            attempt += 1
            await asyncio.sleep(0.1)

    async def _terminate_process(self):
        try:
            await asyncio.gather(self._killer(), self.proc.wait())

            self.returncode = self.proc.returncode
        finally:
            self.proc = None

    async def on_server_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.read_messages_task = asyncio.create_task(self._read_messages())

    async def run(self):
        with tempfile.TemporaryDirectory() as workdir_str:
            self.workdir = Path(workdir_str)
            self.server = await asyncio.start_unix_server(
                    self.on_server_connect,
                    path=self.workdir / "socket")

            self.proc = await asyncio.create_subprocess_exec(
                    *self.get_commandline())

            try:
                await self.main_loop()
            finally:
                if self.proc is not None:
                    await self._terminate_process()


class BottomComponent(SubprocessComponent):
    """
    Component that interfaces with a controller program.

    This is the remote controlled by a TopComponent
    """
    def __init__(self, path: Path, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.read_messages_task: asyncio.Task | None = None
        self.returncode: int | None = None
        self.workdir: Path | None = None

    async def run(self):
        self.reader, self.writer = await asyncio.open_unix_connection(path=self.path)
        self.read_messages_task = asyncio.create_task(self._read_messages())
        await self.main_loop()
