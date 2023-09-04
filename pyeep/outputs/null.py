from __future__ import annotations

from typing import Type

from ..color import Color
from ..component.aio import AIOComponent
from ..component.base import export
from ..messages.component import Shutdown
from .base import OutputController
from .color import ColorOutput, ColorOutputController
from .power import PowerOutput, PowerOutputController


class NullOutput(PowerOutput, ColorOutput, AIOComponent):
    """
    Output that does nothing besides tracking the last set power value
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("rate", 20)
        super().__init__(**kwargs)
        self.power: float = 0.0
        self.color: Color = Color()

    @property
    def description(self) -> str:
        return "Null output"

    def get_output_controller(self, bottom: bool = False) -> Type[OutputController]:
        class Controller(PowerOutputController, ColorOutputController):
            pass
        return Controller

    @export
    def set_power(self, power: float):
        self.power = power

    @export
    def set_color(self, color: Color):
        self.color = color

    async def run(self):
        while True:
            msg = await self.next_message()
            match msg:
                case Shutdown():
                    break
