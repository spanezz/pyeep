import asyncio
import logging
import os
import secrets
from pathlib import Path
from typing import override

from aiohttp import web

from pyeep.app.base import BaseApp
from pyeep.component.component import Component
from pyeep.models.messages.component import Shutdown
from . import app_main, app_api

log = logging.getLogger(__name__)


class PyeepServer(Component):
    """HTTP server acting as the main hub for pyeep apps."""

    def __init__(self, host: str = "localhost", port: int = 8001) -> None:
        super().__init__(name="server")
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe()
        self.main = app_main.Main()
        self.api = app_api.API(token=self.token)
        self.webapp = self.main.make_app()
        self.webapp.add_subapp("/pyeep/", self.api.make_app())

    def write_token(self, path: Path) -> None:
        fd = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC, mode=0o400
        )
        with open(fd, mode="wt") as out:
            out.write(self.token)

    async def shutdown_requested(self) -> None:
        """Close client websockets when a shutdown has been requested."""
        # Send a shutdown message to each connected client
        shutdown_msg = Shutdown(src=())
        try:
            notify_tasks = [
                asyncio.create_task(ws.send_str(shutdown_msg.as_json))
                for ws in self.api.clients.values()
            ]
            if notify_tasks:
                await asyncio.wait(notify_tasks, timeout=2)
        except TimeoutError:
            self.log.warning("timed out when sending shutdown signals")
        # Close the websockets for all clients
        try:
            close_tasks = [
                asyncio.create_task(ws.close())
                for ws in self.api.clients.values()
            ]
            if close_tasks:
                await asyncio.wait(close_tasks, timeout=2)
        except TimeoutError:
            self.log.warning("timed out when closing websocket connections")

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
        super().__init__(name="hub")
        self.webapp = PyeepServer()
        self.web_token_path = Path(".webtoken")

    @override
    async def main_init(self) -> None:
        await super().main_init()
        self.webapp.write_token(self.web_token_path)

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        tg.create_task(self.webapp.run())

    @override
    async def main_shutdown_requested(self) -> None:
        await super().main_shutdown_requested()
        try:
            await self.webapp.shutdown_requested()
        except Exception as e:
            log.error("Failed to shut down clients cleanly: %s", e, exc_info=e)

    @override
    async def main_shutdown(self) -> None:
        self.web_token_path.unlink(missing_ok=True)
        await super().main_shutdown()


if __name__ == "__main__":
    App.run()
