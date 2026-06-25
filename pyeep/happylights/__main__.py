import argparse
from typing import Unpack, override

from pyeep.animator import ColorAnimator
from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import BaseAppArgs
from pyeep.happylights.happylights import HappyLights
from pyeep.models.animation import AnimationPrimitive
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.models.messages.color import SetColor
from pyeep.nodes import PublicComponent
from pyeep.nodes.bluetooth import BLEComponentArgs


class Lights(HappyLights, PublicComponent):
    """Lights control."""

    hub: "LightsApp"

    def __init__(self, **kwargs: Unpack[BLEComponentArgs]) -> None:
        super().__init__(**kwargs)
        self.animator = ColorAnimator(
            name="colors", frame_duration_ns=50_000_000
        )

    async def animator_task(self) -> None:
        async for value in self.animator.values():
            await self.set_color(value)

    @override
    async def init(self) -> None:
        await super().init()
        await self.start_task(self.animator_task())

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
        self.lights = Lights(name="lights", device=self.args.addr, hub=self)

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr",
            "-a",
            type=str,
            required=True,
            help="Bluetooth address of the device",
        )
        return parser

    @override
    async def init(self) -> None:
        await super().init()
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
