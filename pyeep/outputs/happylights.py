from __future__ import annotations

from typing import Type

from .. import bluetooth
from ..app import Message
from ..aio import export
from ..types import Color
from .base import OutputController
from .color import ColorOutput, ColorOutputController

COMMAND_CHARACTERISTIC = '0000ffd9-0000-1000-8000-00805f9b34fb'


class SetColor(Message):
    """
    Internal use only
    """
    def __init__(self, color: Color, **kwargs):
        super().__init__(**kwargs)
        self.color = color

    def __str__(self) -> str:
        return (
            super().__str__() +
            f"(red={self.color[0]:.3f}, green={self.color[1]:.3f}, blue={self.color[2]:.3f})"
        )


class HappyLights(ColorOutput, bluetooth.BluetoothComponent):
    """
    Control a Bluetooth light strip using the Triones or HappyLighting
    protocol.
    """
    # See https://github.com/sysofwan/ha-triones
    # See https://github.com/nfd/happylighting

    def __init__(self, **kwargs):
        kwargs.setdefault("rate", 32)
        super().__init__(**kwargs)
        self.red: int = 0
        self.green: int = 0
        self.blue: int = 0

    def get_output_controller(self) -> Type[OutputController]:
        return ColorOutputController

    @staticmethod
    def cmd_color(r: int, g: int, b: int) -> bytes:
        return bytes([0x56, r, g, b, 0x00, 0xf0, 0xaa])

    @staticmethod
    def cmd_white(intensity: int) -> bytes:
        return bytes([0x56, 0, 0, 0, intensity, 0x0f, 0xaa])

    @staticmethod
    def cmd_on() -> bytes:
        return bytes([0xcc, 0x23, 0x33])

    @staticmethod
    def cmd_off() -> bytes:
        return bytes([0xcc, 0x24, 0x33])

    @export
    def set_color(self, color: Color):
        self.receive(SetColor(color=color))

    async def run_message(self, msg: Message):
        match msg:
            case SetColor():
                cmd = self.cmd_color(
                     int(round(msg.color[0] * 255)),
                     int(round(msg.color[1] * 255)),
                     int(round(msg.color[2] * 255)),
                )
                self.logger.debug("HappyLights command: %s", " ".join(f"{c:x}" for c in cmd))
                await self.client.write_gatt_char(COMMAND_CHARACTERISTIC, cmd)
