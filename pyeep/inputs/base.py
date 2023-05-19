from __future__ import annotations

from enum import StrEnum
from typing import Type

from ..messages import Message
from ..app.component import Component, ModeMixin, export
from ..gtk import Controller, ControllerWidget, Gio, GLib, Gtk


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


class InputActiveStateChanged(Message):
    """
    Notify a change of active state for an input
    """
    def __init__(self, *, input: "Input", value: bool, **kwargs):
        super().__init__(**kwargs)
        self.input = input
        self.value = value

    def __str__(self) -> str:
        return super().__str__() + f"(input={self.input}, value={self.value})"


class Input(ModeMixin, Component):
    """
    Generic base for component managing inputs
    """
    def get_input_controller(self) -> Type["InputController"]:
        return InputController

    def get_connected_state(self) -> ConnectedState:
        """
        Get the current connected state for the input
        """
        return ConnectedState.CONNECTED

    @property
    def is_active(self) -> bool:
        """
        Check if the input is active
        """
        raise NotImplementedError(f"{self.__class__.__name__}.is_active not implemented")

    @export
    def set_active(self, active: bool) -> None:
        """
        Change the active state for the input.

        The function is expected to be idempotent
        """
        raise NotImplementedError(f"{self.__class__.__name__}.set_active not implemented")


class BasicActiveMixin(Input):
    """
    Basic implementation of activity tracking
    """
    def __init__(self, *, active: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.active = active

    @property
    def is_active(self) -> bool:
        return self.active

    @export
    def set_active(self, active: bool) -> None:
        if active == self.active:
            return
        self.active = active
        self.send(InputActiveStateChanged(input=self, value=active))


class InputControllerWidget(ControllerWidget):
    """
    Controller widget with common UI for managing inputs
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connected = Gtk.Image(icon_name="user-offline")
        self.label_box.prepend(self.connected)
        self.active = Gtk.Switch()
        self.label_box.prepend(self.active)

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
            case InputActiveStateChanged():
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
