from __future__ import annotations

from enum import StrEnum
from typing import TypeVar, Type

from ..gtk import Gtk
from .base import Component
from .controller import Controller, ControllerWidget
from ..messages import Message

C = TypeVar("C", bound="ConnectedComponent")


class ConnectedStateChanged(Message):
    """
    Notify a change of connected state for an input
    """
    def __init__(self, *, value: ConnectedState, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    def __str__(self) -> str:
        return super().__str__() + f"(value={self.value})"


class ConnectedState(StrEnum):
    """
    Connection state of a component
    """
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class ConnectedComponent(Component):
    """
    Input that can be connected/disconnected
    """
    def get_connected_state(self) -> ConnectedState:
        """
        Get the current connected state for the input
        """
        return ConnectedState.CONNECTED


class ConnectedControllerWidget(ControllerWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
                self.connected.set_tooltip_text(state)
            case ConnectedState.DISCONNECTED:
                self.connected.set_from_icon_name("user-offline")
                self.connected.set_tooltip_text(state)


class ConnectedController(Controller[C]):
    """
    User interface side for an input (controller and view)
    """
    def get_widget_class(self) -> Type[ControllerWidget]:
        Widget = super().get_widget_class()
        return type("ComponentWidget", (ConnectedControllerWidget, Widget), {})

    def receive(self, msg: Message):
        match msg:
            case ConnectedStateChanged():
                if msg.src == self.component:
                    self.widget.set_connected_state(msg.value)
            case _:
                super().receive(msg)

    def build(self) -> ControllerWidget:
        """
        Build the input view
        """
        cw = super().build()
        cw.set_connected_state(self.component.get_connected_state())
        return cw
