import asyncio
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Callable, Awaitable, override

from aiohttp import web

from pyeep.app.base import BaseApp
from pyeep.component.component import Component
from pyeep.models import load_primitive
from pyeep.models.messages import Message

log = logging.getLogger(__name__)


class PyeepServer(Component):
    """HTTP server acting as the main hub for pyeep apps."""

    def __init__(self, host: str = "localhost", port: int = 8001) -> None:
        super().__init__(name="server")
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe()
        self.webapp = web.Application(middlewares=[self.check_token])
        self.webapp.add_routes(
            [
                web.get("/", self.home),
                web.get("/pyeep/{name}", self.messages),
            ]
        )
        self.clients: dict[str, web.WebSocketResponse] = {}

    def write_token(self, path: Path) -> None:
        fd = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC, mode=0o400
        )
        with open(fd, mode="wt") as out:
            out.write(self.token)

    @web.middleware
    async def check_token(
        self,
        request: web.BaseRequest,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        """Check for the presence of an auth token."""
        if (token := request.cookies.get("Token")) is None:
            raise web.HTTPForbidden(reason="missing token")
        if token != self.token:
            raise web.HTTPForbidden(reason="invalid token")
        return await handler(request)

    async def home(self, request: web.BaseRequest) -> web.Response:
        return web.Response(text="PYEEP")

    async def fanout(self, msg: Message) -> None:
        """Send a message to all connected clients but the one it comes from."""
        for name, ws in self.clients.items():
            if msg.src and msg.src[0] == name:
                continue
            await ws.send_str(msg.as_json)

    async def messages(self, request: web.BaseRequest) -> web.WebSocketResponse:
        client_name = request.match_info["name"]
        if client_name in self.downstream:
            raise web.HTTPForbidden(
                reason=f"client {client_name!r} already registered"
            )

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.clients[client_name] = ws = ws
        try:
            async for wsmsg in ws:
                match wsmsg.type:
                    case web.WSMsgType.text:
                        msg = load_primitive(json.loads(wsmsg.data))
                        if isinstance(msg, Message):
                            await self.fanout(msg)
                    case web.WSMsgType.binary:
                        log.warning("received unexpected binary message", wsmsg)
                    case web.WSMsgType.close:
                        break
                    case web.WSMsgType.error:
                        log.error("received unexpected error message", wsmsg)
                        break
        finally:
            del self.clients[client_name]
        return ws

    async def run(self) -> None:
        runner = web.AppRunner(self.webapp)
        await runner.setup()
        try:
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            log.info(
                "HTTP server started on http://%s:%d", self.host, self.port
            )
            while True:
                # TODO: wait for a Shutdown signal
                await asyncio.sleep(3600)
        finally:
            await runner.cleanup()
            log.info("HTTP server shut down")


class App(BaseApp):
    """Pyeep main coordination app."""

    def __init__(self) -> None:
        super().__init__()
        self.webapp = PyeepServer()
        self.web_token_path = Path(".webtoken")

    @override
    def main_init(self) -> None:
        super().main_init()
        self.webapp.write_token(self.web_token_path)

    @override
    def main_loop(self) -> None:
        """
        Main loop.

        The application will shut down after this function returns.
        """
        try:
            asyncio.run(self.webapp.run())
        except KeyboardInterrupt:
            pass

    @override
    def main_shutdown(self) -> None:
        self.web_token_path.unlink(missing_ok=True)
        super().main_shutdown()


if __name__ == "__main__":
    App.run()
