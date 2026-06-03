import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import override

import aiohttp

from pyeep.app.base import BaseApp, AppShutdownEvent
from pyeep.component.component import Component
from pyeep.models import load_primitive
from pyeep.models.messages import Message
from pyeep.models.messages.component import NewComponent

log = logging.getLogger(__name__)


class PyeepClient(Component):
    """Connect to a Pyeep HTTP server."""

    def __init__(
        self,
        *,
        name: str,
        host: str = "localhost",
        port: int = 8001,
        token_file: Path = Path(".webtoken"),
    ) -> None:
        super().__init__(name=name)
        self.host = host
        self.port = port
        self.baseurl = f"http://{self.host}:{self.port}"
        self.token = token_file.read_text()
        self.ws: aiohttp.ClientWebSocketResponse | None = None

    @override
    async def route_up(self, msg: Message) -> None:
        if self.ws is None:
            return
        await self.ws.send_str(msg.as_json)

    async def connect(self) -> None:
        async with aiohttp.ClientSession(
            cookies={"Token": self.token}
        ) as session:
            async with session.get(self.baseurl) as response:
                response.raise_for_status()
                content = await response.text()
                if content != "PYEEP":
                    raise RuntimeError(
                        f"Server at {self.baseurl}"
                        " does not look like a pyeep server"
                    )

            async with session.ws_connect(
                f"{self.baseurl}/pyeep/{self.name}"
            ) as ws:
                try:
                    self.ws = ws
                    await self.send(NewComponent())
                    async for wsmsg in ws:
                        match wsmsg.type:
                            case aiohttp.WSMsgType.TEXT:
                                msg = load_primitive(json.loads(wsmsg.data))
                                if isinstance(msg, Message):
                                    await self.route(msg)
                            case aiohttp.WSMsgType.CLOSE:
                                break
                            case _:
                                log.error(
                                    "received unexpected %s message %r",
                                    wsmsg.type,
                                    wsmsg,
                                )
                finally:
                    self.ws = None


class ClientApp(BaseApp):
    """Base for pyeep client apps."""

    def __init__(self, *, name: str) -> None:
        super().__init__(name=name)
        self.webclient = PyeepClient(
            name=name,
            host=self.args.host,
            port=self.args.port,
            token_file=self.args.token,
        )

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--host", "-H", default="localhost", help="HTTP host to connect to"
        )
        parser.add_argument(
            "--port",
            "-P",
            type=int,
            default=8001,
            help="HTTP port to connect to",
        )
        parser.add_argument(
            "--token",
            type=Path,
            default=Path(".webtoken"),
            help="file with the authentication token",
        )
        return parser

    async def client_task(self) -> None:
        await self.webclient.connect()
        await self.main_event_queue.put(AppShutdownEvent("Server disconnected"))

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        tg.create_task(self.client_task())


if __name__ == "__main__":
    ClientApp.run()
