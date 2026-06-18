import argparse
import asyncio
import logging
from typing import Unpack, override

from pyeep.animator import ColorAnimator
from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import BaseAppArgs
from pyeep.happylights.happylights import HappyLights
from pyeep.models.animation import AnimationPrimitive
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.models.messages.color import SetColor
from pyeep.nodes import ComponentArgs, PublicComponent


class Lights(PublicComponent):
    """Lights control."""

    hub: "LightsApp"

    def __init__(
        self, addr: str | None, **kwargs: Unpack[ComponentArgs]
    ) -> None:
        super().__init__(**kwargs)
        self.animator = ColorAnimator(
            name="colors", frame_duration_ns=50_000_000
        )
        self.lights: HappyLights | None = None
        if addr:
            self.lights = HappyLights(
                device=addr,
                log=logging.getLogger(f"{self.get_logger_name()}.ble"),
            )

    async def animator_task(self) -> None:
        async for value in self.animator.values():
            await self.set_color(value)

    async def set_color(self, color: Color) -> None:
        if self.lights is not None:
            await self.lights.set_color(color)
        # self.hub.interface.term.add_line(
        #     [(str(color), f"Color set to {color}.")]
        # )

    async def main(self) -> None:
        async with asyncio.TaskGroup() as tg:
            if self.lights is not None:
                tg.create_task(self.supervise_coroutine(self.lights.main()))
            tg.create_task(self.supervise_coroutine(self.animator_task()))

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case SetColor():
                match msg.color:
                    case Color():
                        self.hub.interface.term.add_line(
                            [(str(msg.color), f"Color set to {msg.color}.")]
                        )
                        await self.set_color(msg.color)
                    case AnimationPrimitive():
                        self.hub.interface.term.add_line(
                            [
                                (
                                    str(getattr(msg.color, "color", "#dddddd")),
                                    f"Animate {msg.color}.",
                                )
                            ]
                        )
                        self.animator.add_at_next_tick(
                            msg.color.get_animation()
                        )


class LightsApp(ApplicationAsyncCmdClientApp):
    """Control a happylights bluetooth light source."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.lights = Lights(name="lights", addr=self.args.addr, hub=self)

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    @override
    async def start_main_tasks(self) -> None:
        await super().start_main_tasks()
        await self.add_component(self.lights)
        await self.start_task(self.lights.main())

    async def cmd_color(self, r: float, g: float, b: float) -> None:
        """
        Set the color to float r g b values.

        Example:

          color 1 0.5 0
        """
        await self.lights.set_color(Color(red=r, green=g, blue=b))


if __name__ == "__main__":
    LightsApp.run()
