from __future__ import annotations

from typing import Type

from ..app import Component, Message, check_hub
from ..gtk import Gtk, GtkComponent


class NewOutput(Message):
    """
    Notify the instantiation of a new output
    """
    def __init__(self, *, output: "Output", **kwargs):
        super().__init__(**kwargs)
        self.output = output

    def __str__(self):
        return super().__str__() + f"({self.output.description})"


class Output(Component):
    """
    Generic base for output components
    """
    def __init__(self, *, rate: int, **kwargs):
        super().__init__(**kwargs)

        # Rate (changes per second) at which this output can take commands
        self.rate = rate

    def __str__(self) -> str:
        return f"Output({self.description})"

    def get_output_controller(self) -> Type["OutputController"]:
        return OutputController

    @property
    def description(self) -> str:
        return self.name


class OutputController(GtkComponent):
    """
    Base class for output controllers.

    A controller implements the backend GLib-based logic to handle an Output,
    and instantiating the frontend view widget
    """
    def __init__(self, *, output: Output, **kwargs):
        kwargs.setdefault("name", "output_model_" + output.name)
        super().__init__(**kwargs)
        self.output = output

        # Group ID
        self.group = Gtk.Adjustment(
                value=0,
                lower=0,
                upper=20,
                step_increment=1,
                page_increment=1,
                page_size=0)

    def build(self) -> Gtk.Grid:
        grid = Gtk.Grid()

        label_name = Gtk.Label(label=self.output.description)
        label_name.wrap = True
        label_name.set_halign(Gtk.Align.START)
        grid.attach(label_name, 0, 0, 3, 1)

        group = Gtk.SpinButton(adjustment=self.group, climb_rate=1.0, digits=0)
        group.set_tooltip_text("Group number")
        grid.attach(group, 0, 1, 1, 1)

        return grid


class OutputsModel(GtkComponent):
    """
    Container for output view widgets
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.output_models: list[OutputController] = []

    def build(self) -> Gtk.Frame:
        w = Gtk.Frame(label="Outputs")
        w.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        w.set_child(box)
        return w

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case NewOutput():
                output_model = self.hub.app.add_component(
                        msg.output.get_output_controller(),
                        output=msg.output)
                self.output_models.append(output_model)
                self.widget.get_child().append(output_model.widget)
