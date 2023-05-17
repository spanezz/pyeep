from __future__ import annotations

from typing import Type

from .. import bluetooth
from ..app import Message, export
from ..gtk import Gtk
from ..color import Color
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
            f"(color={self.color})"
        )


class HappyLights(ColorOutput, bluetooth.BluetoothComponent):
    """
    Control a Bluetooth light strip using the Triones or HappyLighting
    protocol.
    """
    # See https://github.com/sysofwan/ha-triones
    # See https://github.com/nfd/happylighting

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("rate", 32)
        super().__init__(**kwargs)
        self.red: int = 0
        self.green: int = 0
        self.blue: int = 0
        self.brightness: float = 1.0

    def get_output_controller(self) -> Type[OutputController]:
        return HappyLightsOutputController

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
    def set_color(self, color: Color) -> None:
        self.receive(SetColor(color=color))

    @export
    def set_brightness(self, value: float) -> None:
        self.brightness = value

    async def run_message(self, msg: Message) -> None:
        match msg:
            case SetColor():
                color = msg.color * self.brightness
                cmd = self.cmd_color(
                     int(round(color.red * 255)),
                     int(round(color.green * 255)),
                     int(round(color.blue * 255)),
                )
                self.logger.debug("HappyLights command: %s", " ".join(f"{c:x}" for c in cmd))
                await self.client.write_gatt_char(COMMAND_CHARACTERISTIC, cmd)


class HappyLightsOutputController(ColorOutputController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.brightness = Gtk.Adjustment(
                lower=0.0, upper=1.0, step_increment=0.1, page_increment=0.3, value=1)
        self.brightness.connect("value-changed", self.on_brightness)

    def on_brightness(self, adjustment):
        value = self.brightness.get_value()
        self.output.set_brightness(value)

    def build(self) -> Gtk.Grid:
        grid = super().build()
        grid.attach(Gtk.Label(label="Brightness"), 0, 2, 1, 1)

        spinbutton = Gtk.SpinButton()
        spinbutton.set_adjustment(self.brightness)
        spinbutton.set_digits(1)
        grid.attach(spinbutton, 1, 2, 1, 1)
        return grid
