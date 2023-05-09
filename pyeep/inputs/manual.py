from __future__ import annotations

from typing import Type

from ..app import Message, check_hub
from ..gtk import Gtk, GtkComponent
from .base import Input, InputController, InputSetActive, InputSetMode
from .keyboards import Shortcut


class Manual(Input, GtkComponent):
    """
    Dummy manual input used for testing
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active = True

    @property
    def is_active(self) -> bool:
        return self.active

    def build(self) -> None:
        return None

    @property
    def description(self) -> str:
        return "Manual"

    def get_input_controller(self) -> Type["InputController"]:
        return ManualInputController

    @check_hub
    def mode_default(self, value: str):
        if self.is_active:
            self.send(Shortcut(command=value))

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case InputSetActive():
                if msg.input == self:
                    self.active = msg.value
            case InputSetMode():
                if msg.input == self:
                    self.mode = getattr(self, "mode_" + msg.mode)


class ManualInputController(InputController):
    def build(self) -> Gtk.Box:
        grid = super().build()
        pulse = Gtk.Button(label="Pulse")
        pulse.connect("clicked", self.on_pulse)
        grid.attach(pulse, 0, 3, 1, 1)
        return grid

    def on_pulse(self, button):
        self.input.mode("PULSE")
