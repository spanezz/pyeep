import argparse
import asyncio
import json
import time as tm
from pathlib import Path
from typing import Unpack, override

import aiohttp

from pyeep.app.base import AppEvent, AppEventShutdown, BaseApp, BaseAppArgs
from pyeep.models import load_primitive
from pyeep.models.hub import HubConnectInfo
from pyeep.models.messages import Broadcast, Command, Event
from pyeep.nodes import Hub, NodeArgs, PublicComponent, Component
from pyeep.nodes.messages import ComponentAdded, ComponentRemoved


class AppEventSendEvent(AppEvent):
    """Request to send an event up towards the hub."""

    def __init__(self, event: Event) -> None:
        self.event = event

    @override
    def __str__(self) -> str:
        return str(self.event)


class ClientApp(BaseApp):
    """Base for pyeep client apps."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.hub_info: HubConnectInfo | None = None
        if self.args.hub:
            self.hub_info = self.load_hub_info()
        self.ws: aiohttp.ClientWebSocketResponse | None = None

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--hub",
            type=Path,
            help="connect to the pyeep hub using the information in this file",
        )
        return parser

    def load_hub_info(self) -> HubConnectInfo:
        """Wait for the hub info file to exists and load it."""
        attempts = 0
        while attempts < 20:
            try:
                data = self.args.hub.read_text()
            except FileNotFoundError:
                tm.sleep(0.1)
            else:
                return HubConnectInfo.model_validate(json.loads(data))
        raise RuntimeError("Cannot connect to hub after 20 attempts.")

    @override
    async def advertise_component_added(self, component: Component) -> None:
        if isinstance(component, PublicComponent):
            await component.send_event(ComponentAdded())

    @override
    async def advertise_component_removed(self, component: Component) -> None:
        if isinstance(component, PublicComponent):
            await component.send_event(ComponentRemoved())

    async def advertise_public_components(self) -> None:
        """Advertise existing public components to the remote hub."""
        async with asyncio.TaskGroup() as tg:
            for component in self.components.values():
                if not isinstance(component, PublicComponent):
                    continue
                tg.create_task(self.advertise_component_added(component))

    @override
    async def outbound_event(self, msg: Event) -> None:
        if self.ws is None:
            return
        await self.ws.send_str(msg.as_json)

    @override
    async def outbound_broadcast(self, msg: Broadcast) -> None:
        self.log.warning("Ignoring client attempt to send broadcast %s", msg)
        return

    @override
    async def outbound_command(self, msg: Command) -> None:
        self.log.warning("Ignoring client attempt to send command %s", msg)
        return

    async def connect(self) -> None:
        """Connect to the server and handle message traffic."""
        assert self.hub_info is not None
        baseurl = self.hub_info.get_baseurl()
        async with aiohttp.ClientSession(
            cookies={"Token": self.hub_info.token}
        ) as session:
            async with session.get(f"{baseurl}/pyeep/hub/") as response:
                response.raise_for_status()
                content = await response.text()
                if content != "PYEEP":
                    raise RuntimeError(
                        f"Server at {baseurl}"
                        " does not look like a pyeep server"
                    )

            async with session.ws_connect(
                f"{baseurl}/pyeep/hub/{self.name}"
            ) as ws:
                try:
                    self.ws = ws
                    await self.advertise_public_components()
                    async for wsmsg in ws:
                        match wsmsg.type:
                            case aiohttp.WSMsgType.TEXT:
                                match msg := load_primitive(
                                    json.loads(wsmsg.data)
                                ):
                                    case Broadcast():
                                        await self.inbound_broadcast(msg)
                                    case Command():
                                        await self.inbound_command(msg)
                                    case _:
                                        self.log.warning(
                                            "Ignoring unsupported"
                                            " inbound message: %s",
                                            msg,
                                        )
                            case aiohttp.WSMsgType.CLOSE:
                                break
                            case _:
                                self.log.error(
                                    "received unexpected %s message %r",
                                    wsmsg.type,
                                    wsmsg,
                                )
                finally:
                    self.ws = None

    async def client_task(self) -> None:
        if self.hub_info:
            await self.connect()
            await self.main_event_queue.put(
                AppEventShutdown("Server disconnected")
            )

    @override
    async def main_init(self) -> None:
        await super().main_init()
        await self.start_task(self.client_task())

    @override
    async def main_process_event(self, evt: AppEvent) -> None:
        """Process an event from the main event queue."""
        match evt:
            case AppEventSendEvent():
                await self.outbound_event(evt.event)
            case _:
                await super().main_process_event(evt)


if __name__ == "__main__":
    ClientApp.run()
