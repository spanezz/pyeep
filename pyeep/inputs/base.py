from __future__ import annotations

from typing import Type, TypeVar

from ..component.active import ActiveComponent, ActiveController
from ..component.base import Component, check_hub
from ..component.controller import Controller
from ..component.gtk import GtkComponent
from ..component.modes import ModeComponent, ModeController
from ..gtk import Gtk
from ..messages.component import NewComponent
from ..messages.message import Message

C = TypeVar("C", bound="Input")


class Input(ModeComponent, ActiveComponent, Component):
    """
    Generic base for components managing inputs
    """
    def get_controller(self) -> Type["Controller"]:
        return InputController


class InputController(ActiveController[C], ModeController[C]):
    """
    User interface side for an input (controller and view)
    """
    def __init__(self, *, component: Component, **kwargs):
        kwargs.setdefault("name", "input_model_" + component.name)
        super().__init__(component=component, **kwargs)


class InputsModel(GtkComponent):
    """
    Container for output view widgets
    """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.input_models: list[InputController] = []

    def build(self) -> Gtk.Frame:
        w = Gtk.Frame(label="Inputs")
        w.set_vexpand(True)
        w.set_margin_bottom(10)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        w.set_child(box)
        return w

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case NewComponent():
                if isinstance(msg.src, Input):
                    input_model = self.hub.app.add_component(
                            msg.src.get_controller(),
                            component=msg.src)
                    self.input_models.append(input_model)
                    self.widget.get_child().append(input_model.widget)
