import argparse
import asyncio
import json
import logging
import secrets
from pathlib import Path
from typing import Any, override, Unpack

import yaml
from aiohttp import web

from pyeep.app.base import BaseApp, BaseAppArgs
from pyeep.models.hub import HubConnectInfo
from pyeep.models.messages import Broadcast, Command, Event, Message
from pyeep.models.scene import load_scene_description
from pyeep.nodes import Component, Hub
from pyeep.nodes.groups import Groups
from pyeep.nodes.messages import Shutdown, ComponentRemoved
from pyeep.nodes.web import WebComponent, WebHub
from pyeep.scenes.base import WebScene
from pyeep.utils.atomic import atomic_writer

from . import app_api, app_main

log = logging.getLogger(__name__)


class LogEvents(Component):
    """Log incoming events."""

    @override
    async def receive(self, msg: Message) -> None:
        await super().receive(msg)
        match msg:
            case Event():
                self.log.info("Event received: %s", msg)


class Scenes(Component):
    """Container component for scenes."""

    def __init__(self, *, hub: "Hub") -> None:
        super().__init__(name="scenes", hub=hub)
        self.scenes: dict[str, WebScene[Any]] = {}

    async def load(self, data: list[dict[str, Any]]) -> None:
        """Load scenes from a YAML file."""
        for scene_data in data:
            desc = load_scene_description(scene_data)
            scene = desc.make_scene(hub=self.hub)
            assert isinstance(scene, WebScene)
            if scene.name in self.scenes:
                raise RuntimeError(f"scene {scene.name} defined multiple times")
            self.scenes[scene.name] = scene
            await self.hub.add_component(scene)
            self.log.info("Added scene %s - %s", scene.name, scene.desc.label)

    async def main(self) -> None:
        async with asyncio.TaskGroup() as tg:
            for scene in self.scenes.values():
                tg.create_task(self.supervise_coroutine(scene.main()))


class HubApp(BaseApp, WebHub):
    """Pyeep main coordination app."""

    DEFAULT_NAME = "hub"

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.token = secrets.token_urlsafe()
        self.scenes = Scenes(hub=self)
        self.groups = Groups(hub=self, name="groups")
        self.log_events = LogEvents(name="log_events", hub=self)

        self.ui = app_main.Main(hub=self)
        self.api = app_api.API(hub=self)
        self.web_token_path = Path(".webtoken")

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
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
            "--config",
            "-C",
            type=Path,
            help="YAML file with the Hub configuration",
        )
        parser.add_argument(
            "--log-events", action="store_true", help="Log incoming events"
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

    @override
    async def web_send(
        self, component: WebComponent, msg: dict[str, Any]
    ) -> None:
        await self.api.web_send(component, msg)

    @override
    async def outbound_event(self, msg: Event) -> None:
        self.log.warning("Ignoring outbound event %s", msg)

    @override
    async def outbound_broadcast(self, msg: Broadcast) -> None:
        await self.api.fanout_broadcast(msg)

    @override
    async def outbound_command(self, msg: Command) -> None:
        await self.api.fanout_command(msg)

    async def shutdown_clients(self) -> None:
        """Close client websockets when a shutdown has been requested."""
        # Send a shutdown message to each connected client
        try:
            self.log.warning("broadcasting shutdown to clients")
            async with asyncio.timeout(2):
                await self.outbound_broadcast(Shutdown())
        except TimeoutError:
            self.log.warning("timed out when sending shutdown signals")

        # Close the websockets for all clients
        try:
            async with asyncio.timeout(2):
                await self.api.close_all_clients()
        except TimeoutError:
            self.log.warning("timed out when closing websocket connections")

    async def client_disconnected(self, name: str) -> None:
        """Called after a client disconnects."""
        await self.groups.disconnect_by_prefix(name)

    async def webapp_run(self) -> None:
        webapp = self.ui.make_app()
        webapp.add_subapp("/pyeep/", self.api.app)
        runner = web.AppRunner(webapp)
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

    async def load_config(self, source: Path) -> None:
        """Load configuration from the given file."""
        self.log.info("Loading configuration from %s", source)
        data = yaml.safe_load(source.read_text())
        if not isinstance(data, dict):
            raise RuntimeError(f"{source} does not contain a dict")
        if groups := data.get("groups"):
            if not isinstance(groups, list):
                raise RuntimeError(
                    f"{source}:groups does not contain a list of records"
                )
            await self.groups.load(groups)
        if scenes := data.get("scenes"):
            if not isinstance(scenes, list):
                raise RuntimeError(
                    f"{source}:scenes does not contain a list of records"
                )
            await self.scenes.load(scenes)

    @override
    async def main_init(self) -> None:
        await super().main_init()
        await self.add_component(self.scenes)
        await self.add_component(self.groups)
        if self.args.log_events:
            await self.add_component(self.log_events)
        if self.args.config:
            await self.load_config(self.args.config)
        self.write_token(self.web_token_path)

    @override
    async def start_main_tasks(self) -> None:
        await super().start_main_tasks()
        await self.start_task(self.webapp_run())
        await self.start_task(self.scenes.main())

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
