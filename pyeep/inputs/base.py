from __future__ import annotations

from enum import StrEnum
from typing import Type

from ..app.component import ActivityToggleMixin, Component, ModeMixin
from ..gtk import Controller, ControllerWidget, Gio, GLib, Gtk
from ..messages import ComponentActiveStateChanged, Message


class ConnectedState(StrEnum):
    """
    Connection state of an input
    """
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class InputConnectedStateChanged(Message):
    """
    Notify a change of connected state for an input
    """
    def __init__(self, *, input: "Input", value: ConnectedState, **kwargs):
        super().__init__(**kwargs)
        self.input = input
        self.value = value

    def __str__(self) -> str:
        return super().__str__() + f"(input={self.input}, value={self.value})"


class Input(ModeMixin, ActivityToggleMixin, Component):
    """
    Generic base for component managing inputs
    """
    def get_controller(self) -> Type["Controller"]:
        return InputController

    def get_connected_state(self) -> ConnectedState:
        """
        Get the current connected state for the input
        """
        return ConnectedState.CONNECTED


class InputControllerWidget(ControllerWidget):
    """
    Controller widget with common UI for managing inputs
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Stop using the frame label
        label = self.get_label_widget()
        self.set_label_widget(None)

        # Put a CenterBox at the top of the frame instead
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(box)
        box.append(self.grid)

        # Label at the center
        self.header = Gtk.CenterBox()
        box.prepend(self.header)
        self.header.set_center_widget(label)

        # Active state
        self.active = Gtk.Switch()
        self.header.set_start_widget(self.active)

        # Connected status
        self.connected = Gtk.Image(icon_name="user-offline")
        self.header.set_end_widget(self.connected)

    def set_connected_state(self, state: ConnectedState):
        """
        Change the connected state displayed for the input
        """
        match state:
            case ConnectedState.CONNECTED:
                self.connected.set_from_icon_name("user-available")
            case ConnectedState.DISCONNECTED:
                self.connected.set_from_icon_name("user-offline")


class InputController(Controller[Input]):
    """
    User interface side for an input (controller and view)
    """
    Widget = InputControllerWidget

    def __init__(self, *, input: Input, **kwargs):
        kwargs.setdefault("name", "input_model_" + input.name)
        super().__init__(component=input, **kwargs)
        self.input = input

        self.active = Gio.SimpleAction.new_stateful(
                name=self.name.replace("_", "-") + "-active",
                parameter_type=None,
                state=GLib.Variant.new_boolean(self.input.is_active))
        self.active.connect("activate", self.on_activate)
        self.hub.gtk_app.add_action(self.active)

        self.modes = Gtk.ListStore(str, str)
        for info in self.input.list_modes():
            self.modes.append([info.name, info.summary])

    def receive(self, msg: Message):
        match msg:
            case InputConnectedStateChanged():
                if msg.src == self.input:
                    self.widget.set_connected_state(msg.value)
            case ComponentActiveStateChanged():
                if msg.src == self.input and self.active.get_state().get_boolean() != msg.value:
                    self.active.set_state(GLib.Variant.new_boolean(msg.value))

    def on_activate(self, action, parameter):
        new_state = not self.active.get_state().get_boolean()
        self.active.set_state(GLib.Variant.new_boolean(new_state))
        self.input.set_active(new_state)

    def on_mode_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            mode = model[tree_iter][0]
            self.input.set_mode(mode)

    def build(self) -> ControllerWidget:
        """
        Build the input view
        """
        cw = super().build()
        cw.set_connected_state(self.input.get_connected_state())

        cw.active.set_action_name("app." + self.active.get_name())

        if len(self.modes) > 1:
            modes = Gtk.ComboBox(model=self.modes)
            modes.set_id_column(0)
            renderer = Gtk.CellRendererText()
            modes.pack_start(renderer, True)
            modes.add_attribute(renderer, "text", 1)
            modes.set_active_id("default")
            modes.connect("changed", self.on_mode_changed)
            cw.grid.attach(modes, 0, 2, 1, 1)

        return cw
