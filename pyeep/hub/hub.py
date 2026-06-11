import argparse
import asyncio
import json
import logging
import os
import secrets
import tempfile
from pathlib import Path
from typing import override

from aiohttp import web
import yaml

from pyeep.scenes.models import load_scene_description
from pyeep.scenes.base import Scene
from pyeep.app.base import BaseApp
from pyeep.component.component import Component
from pyeep.models.messages.component import Shutdown
from pyeep.models.hub import HubConnectInfo
from pyeep.models.messages import Message
from pyeep.utils.atomic import atomic_writer
from . import app_main, app_api

log = logging.getLogger(__name__)


class Scenes(Component):
    """Container component for scenes."""

    def __init__(self, *, hub: "Hub") -> None:
        super().__init__(name="scenes")
        self.hub = hub
        self.scenes: dict[str, Scene] = {}

    def load(self, source: Path) -> None:
        """Load scenes from a YAML file."""
        data = yaml.safe_load(source.read_text())
        if not isinstance(data, list):
            raise RuntimeError(f"{source} does not contain a list of records")
        for scene_data in data:
            desc = load_scene_description(scene_data)
            scene = desc.make_scene()
            if scene.name in self.scenes:
                raise RuntimeError(
                    f"{source}: scene {scene.name} defined multiple times"
                )
            self.scenes[scene.name] = scene
            self.add_component(scene)

    async def route_up(self, msg: Message) -> None:
        """Fanout the message to connected clients."""
        await self.hub.app_api.fanout(msg)

    async def main(self) -> None:
        async with asyncio.TaskGroup() as tg:
            for scene in self.scenes.values():
                tg.create_task(scene.main())


class Hub(BaseApp):
    """Pyeep main coordination app."""

    def __init__(self) -> None:
        super().__init__(name="hub")
        self.token = secrets.token_urlsafe()
        self.scenes = Scenes(hub=self)
        if self.args.scenes:
            self.scenes.load(self.args.scenes)
        self.app_main = app_main.Main(hub=self)
        self.app_api = app_api.API(hub=self)
        self.webapp = self.app_main.app
        self.webapp.add_subapp("/pyeep/", self.app_api.app)
        self.web_token_path = Path(".webtoken")

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--host",
            "-H",
            default="localhost",
            help="hostname to use to open listening socket",
        )
        parser.add_argument(
            "--port",
            "-P",
            type=int,
            default=8001,
            help="port to use to open listening socket",
        )
        parser.add_argument(
            "--scenes",
            "-s",
            type=Path,
            help="YAML file describing the scenes to load",
        )
        return parser

    def write_token(self, path: Path) -> None:
        """Write out information needed to connect to the server."""
        if path.exists():
            raise RuntimeError(
                f"{path} already exists: is another server running?"
            )
        info = HubConnectInfo(
            host=self.args.host, port=self.args.port, token=self.token
        )
        with atomic_writer(path, mode="wt", chmod=0o400) as out:
            json.dump(info.model_dump(), out)

    async def process_message_from_client(self, msg: Message) -> None:
        """Process a message received from a client."""
        await self.scenes.route(msg)

    async def shutdown_clients(self) -> None:
        """Close client websockets when a shutdown has been requested."""
        # Send a shutdown message to each connected client
        shutdown_msg = Shutdown(src=())
        try:
            notify_tasks = [
                asyncio.create_task(ws.send_str(shutdown_msg.as_json))
                for ws in self.app_api.clients.values()
            ]
            if notify_tasks:
                await asyncio.wait(notify_tasks, timeout=2)
        except TimeoutError:
            self.log.warning("timed out when sending shutdown signals")
        # Close the websockets for all clients
        try:
            close_tasks = [
                asyncio.create_task(ws.close())
                for ws in self.app_api.clients.values()
            ]
            if close_tasks:
                await asyncio.wait(close_tasks, timeout=2)
        except TimeoutError:
            self.log.warning("timed out when closing websocket connections")

    async def webapp_run(self) -> None:
        runner = web.AppRunner(self.webapp)
        await runner.setup()
        try:
            site = web.TCPSite(runner, self.args.host, self.args.port)
            await site.start()
            log.info(
                "HTTP server started on http://%s:%d",
                self.args.host,
                self.args.port,
            )
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
            log.info("HTTP server shut down")

    @override
    async def main_init(self) -> None:
        await super().main_init()
        self.write_token(self.web_token_path)

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        tg.create_task(self.webapp_run())
        tg.create_task(self.scenes.main())

    @override
    async def main_shutdown_requested(self) -> None:
        await super().main_shutdown_requested()
        try:
            await self.shutdown_clients()
        except Exception as e:
            log.error("Failed to shut down clients cleanly: %s", e, exc_info=e)

    @override
    async def main_shutdown(self) -> None:
        self.web_token_path.unlink(missing_ok=True)
        await super().main_shutdown()
