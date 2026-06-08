import asyncio
import argparse
import logging
from typing import override

from pyeep.app.asynccmd import ApplicationAsyncCmd, AsyncCmdQuit
from pyeep.app.base import AppShutdownEvent
from pyeep.app.client import ClientApp
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.happylights.happylights import HappyLights
from pyeep.models.messages.color import SetGroupColor


class LightsCmd(ApplicationAsyncCmd):
    """Interactive lights control."""

    def __init__(self, lights_app: "LightsApp") -> None:
        super().__init__()
        self.lights_app = lights_app

    async def do_quit(self, arg) -> None:
        raise AsyncCmdQuit()

    async def do_color(self, arg) -> None:
        r, g, b = [float(a) for a in arg.split()]
        await self.lights_app.set_color(Color(red=r, green=g, blue=b))


class LightsApp(ClientApp):
    """Control a happylights bluetooth light source."""

    def __init__(
        self, *, name: str = "happylights", handle_sigterm_sigint: bool = True
    ) -> None:
        super().__init__(name=name, handle_sigterm_sigint=handle_sigterm_sigint)
        self.lights: HappyLights | None = None
        if self.args.addr:
            self.lights = HappyLights(
                device=self.args.addr, log=logging.getLogger(f"{self.name}.ble")
            )
        self.cmd = LightsCmd(self)

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    async def cmd_task(self) -> None:
        await self.cmd.async_cmdloop()
        await self.main_event_queue.put(AppShutdownEvent("User quit"))

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        if self.lights is not None:
            tg.create_task(self.lights.main())
        tg.create_task(self.cmd_task())

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case SetGroupColor():
                # TODO: actual animator support
                # TODO: match group
                await self.set_color(Color(red=0.5, green=0, blue=0))

    async def set_color(self, color: Color) -> None:
        if self.lights is not None:
            await self.lights.set_color(Color(red=0.5, green=0, blue=0))
            await asyncio.sleep(0.3)
            await self.lights.set_color(Color(red=0, green=0, blue=0))
        await self.cmd.term_print(f"Color set to {color}.", style=str(color))


if __name__ == "__main__":
    LightsApp.run()
