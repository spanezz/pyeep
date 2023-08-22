from __future__ import annotations

from typing import Type, TypeVar

from ..gtk import Gio, GLib, Gtk
from ..messages.component import ComponentActiveStateChanged
from ..messages.message import Message
from .base import Component, export
from .controller import Controller, ControllerWidget

C = TypeVar("C", bound="ActiveComponent")


class ActiveComponent(Component):
    """
    Mixin for components that can be activated and deactivated
    """
    @property
    def is_active(self) -> bool:
        """
        Check if the component is active
        """
        raise NotImplementedError(f"{self.__class__.__name__}.is_active not implemented")

    @export
    def set_active(self, active: bool) -> None:
        """
        Change the active state for the component.

        The function is expected to be idempotent
        """
        raise NotImplementedError(f"{self.__class__.__name__}.set_active not implemented")


class SimpleActiveComponent(ActiveComponent):
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
        self.send(ComponentActiveStateChanged(value=active))


class ActiveControllerWidget(ControllerWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Active state
        self.active = Gtk.Switch()
        self.header.set_start_widget(self.active)


class ActiveController(Controller[C]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.active = Gio.SimpleAction.new_stateful(
                name=self.name.replace("_", "-") + "-active",
                parameter_type=None,
                state=GLib.Variant.new_boolean(self.component.is_active))
        self.active.connect("activate", self.on_activate)
        self.hub.gtk_app.add_action(self.active)

    def get_widget_class(self) -> Type[ControllerWidget]:
        Widget = super().get_widget_class()
        return type("InputControllerWidget", (ActiveControllerWidget, Widget), {})

    def receive(self, msg: Message):
        match msg:
            case ComponentActiveStateChanged():
                if msg.src == self.component and self.active.get_state().get_boolean() != msg.value:
                    self.active.set_state(GLib.Variant.new_boolean(msg.value))

    def on_activate(self, action, parameter):
        new_state = not self.active.get_state().get_boolean()
        self.active.set_state(GLib.Variant.new_boolean(new_state))
        self.component.set_active(new_state)

    def build(self) -> ControllerWidget:
        """
        Build the component view
        """
        cw = super().build()
        cw.active.set_action_name("app." + self.active.get_name())
        return cw
