from __future__ import annotations

from typing import Type

from ..app import Component, Message, check_hub
from ..gtk import Gio, GLib, Gtk, GtkComponent, Controller
from .. import messages


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


class OutputController(Controller):
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
                upper=99,
                step_increment=1,
                page_increment=1,
                page_size=0)

        self.pause = Gio.SimpleAction.new_stateful(
                name=self.name.replace("_", "-") + "-pause",
                parameter_type=None,
                state=GLib.Variant.new_boolean(False))
        self.pause.connect("change-state", self.on_pause)
        self.hub.app.gtk_app.add_action(self.pause)

        self.manual = Gio.SimpleAction.new_stateful(
                name=self.name.replace("_", "-") + "-manual",
                parameter_type=None,
                state=GLib.Variant.new_boolean(False))
        self.manual.connect("change-state", self.on_manual)
        self.hub.app.gtk_app.add_action(self.manual)

    def in_group(self, group: int) -> bool:
        """
        Check if this output is in the given group
        """
        return self.group.get_value() == group

    @property
    def is_paused(self) -> bool:
        return self.pause.get_state().get_boolean()

    @property
    def is_manual(self) -> bool:
        return self.manual.get_state().get_boolean()

    @check_hub
    def on_pause(self, action, parameter):
        """
        When the pause mode is disabled, restore the previous value
        """
        new_state = not self.pause.get_state().get_boolean()
        self.set_paused(new_state)

    @check_hub
    def on_manual(self, action, parameter):
        """
        When the manual mode is disabled, leave the previous value
        """
        new_state = not self.manual.get_state().get_boolean()
        self.set_manual(new_state)

    @check_hub
    def set_paused(self, paused: bool):
        """
        Enter/exit pause mode
        """
        self.pause.set_state(GLib.Variant.new_boolean(paused))

    @check_hub
    def set_manual(self, manual: bool):
        """
        When the manual mode is disabled, leave the previous value
        """
        self.manual.set_state(GLib.Variant.new_boolean(manual))

    @check_hub
    def emergency_stop(self):
        """
        Emergency stop of this output
        """
        self.set_paused(True)

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case messages.EmergencyStop():
                self.emergency_stop()
            case messages.Pause():
                if self.in_group(msg.group):
                    self.set_paused(True)
            case messages.Resume():
                if self.in_group(msg.group):
                    self.set_paused(False)

    def build(self) -> Gtk.Grid:
        grid = Gtk.Grid()

        label_name = Gtk.Label(label=self.output.description)
        label_name.wrap = True
        label_name.set_halign(Gtk.Align.START)
        grid.attach(label_name, 0, 0, 3, 1)

        group = Gtk.SpinButton(adjustment=self.group, climb_rate=1.0, digits=0)
        group.set_tooltip_text("Group number")
        grid.attach(group, 0, 1, 1, 1)

        pause = Gtk.ToggleButton(label="Paused")
        pause.set_action_name("app." + self.pause.get_name())
        grid.attach(pause, 1, 1, 1, 1)

        manual = Gtk.ToggleButton(label="Manual")
        manual.set_action_name("app." + self.manual.get_name())
        grid.attach(manual, 2, 1, 1, 1)

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
        w.set_margin_bottom(10)
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
