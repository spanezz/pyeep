import asyncio
import argparse
import cmd
import logging
from typing import override

import rich

from pyeep.app.client import ClientApp
from pyeep.app.sync import SyncClientApp
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.happylights.happylights import HappyLights
from pyeep.models.messages.color import SetGroupColor


class LightsApp(ClientApp):
    """Control a happylights bluetooth light source."""

    def __init__(
        self, *, name: str, handle_sigterm_sigint: bool = True
    ) -> None:
        super().__init__(name=name, handle_sigterm_sigint=handle_sigterm_sigint)
        self.lights = HappyLights(
            device=self.args.addr, log=logging.getLogger(f"{self.name}.ble")
        )

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        tg.create_task(self.lights.main())

    @override
    async def receive(self, msg: Message) -> None:
        print("RECV", msg)
        match msg:
            case SetGroupColor():
                print("SGC")
                # TODO: actual animator support
                # TODO: match group
                await self.lights.set_color(Color(red=0.5, green=0, blue=0))
                await self.lights.set_brightness(1.0)
                await asyncio.sleep(0.3)
                await self.lights.set_brightness(0)


class LightsCli(SyncClientApp, cmd.Cmd):
    """Interacively send pyeep messages."""

    app: LightsApp

    def __init__(self):
        SyncClientApp.__init__(
            self, app=LightsApp(name="lightscli", handle_sigterm_sigint=False)
        )
        cmd.Cmd.__init__(self)

    @override
    def main(self) -> None:
        self.cmdloop()

    def do_quit(self, arg) -> bool:
        return True

    def do_EOF(self, arg) -> bool:
        return True

    def do_color(self, arg) -> None:
        r, g, b = [float(a) for a in arg.split()]
        self.run_async(self.app.lights.set_color(Color(red=r, green=g, blue=b)))

    def do_bright(self, arg) -> None:
        val = float(arg)
        self.run_async(self.app.lights.set_brightness(val))


def main():
    cli = LightsCli()
    cli.run()


if __name__ == "__main__":
    main()
