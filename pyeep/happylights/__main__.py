import asyncio
import argparse
import logging
from typing import override

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.happylights.happylights import HappyLights
from pyeep.models.messages.color import SetGroupColor
from pyeep.animator import ColorAnimator
from pyeep.models.animation import AnimationPrimitive


class LightsApp(ApplicationAsyncCmdClientApp):
    """Control a happylights bluetooth light source."""

    def __init__(
        self, *, name: str = "happylights", handle_sigterm_sigint: bool = True
    ) -> None:
        super().__init__(name=name, handle_sigterm_sigint=handle_sigterm_sigint)
        self.animator = ColorAnimator(
            name="colors", frame_duration_ns=50_000_000
        )
        self.lights: HappyLights | None = None
        if self.args.addr:
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

    async def animator_task(self) -> None:
        async for value in self.animator.values():
            await self.set_color(value)

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        if self.lights is not None:
            tg.create_task(self.lights.main())
        tg.create_task(self.animator_task())

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case SetGroupColor():
                match msg.color:
                    case Color():
                        await self.set_color(msg.color)
                    case AnimationPrimitive():
                        self.animator.add_at_next_tick(
                            msg.color.get_animation()
                        )

    async def set_color(self, color: Color) -> None:
        if self.lights is not None:
            await self.lights.set_color(color)
        # self.interface.term.add_line([(str(color), f"Color set to {color}.")])

    async def cmd_color(self, arg) -> None:
        """
        Set the color to float r g b values.

        Example:

          color 1 0.5 0
        """
        r, g, b = [float(a) for a in arg.split()]
        await self.set_color(Color(red=r, green=g, blue=b))


if __name__ == "__main__":
    LightsApp.run()
