from __future__ import annotations

from typing import Type

from ..app import check_hub
from ..app.component import BasicActiveMixin
from ..gtk import ControllerWidget, Gtk, GtkComponent
from .base import Input, InputController
from .keyboards import Shortcut


class Manual(BasicActiveMixin, Input, GtkComponent):
    """
    Dummy manual input used for testing
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("active", True)
        super().__init__(**kwargs)

    def build(self) -> None:
        return None

    @property
    def description(self) -> str:
        return "Manual"

    def get_controller(self) -> Type["InputController"]:
        return ManualInputController

    @check_hub
    def mode_default(self, value: str):
        if self.is_active:
            self.send(Shortcut(command=value))


class ManualInputController(InputController):
    def build(self) -> ControllerWidget:
        cw = super().build()
        pulse = Gtk.Button(label="Pulse")
        pulse.connect("clicked", self.on_pulse)
        cw.grid.attach(pulse, 0, 3, 1, 1)
        return cw

    def on_pulse(self, button):
        self.input.mode("PULSE")
