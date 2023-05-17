from __future__ import annotations

from typing import Type

from ..app import Component, Message
from ..app.component import ModeMixin
from ..gtk import Gio, GLib, Gtk, Controller


class InputSetActive(Message):
    """
    Activate/deactivate an input
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

    @property
    def is_active(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__}._is_active not implemented")


class InputController(Controller[Input]):
    """
    User interface side for an input (controller and view)
    """
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

    def is_active(self) -> bool:
        return self.active.get_state().get_boolean()

    def on_activate(self, action, parameter):
        new_state = not self.active.get_state().get_boolean()
        self.active.set_state(GLib.Variant.new_boolean(new_state))
        self.send(InputSetActive(input=self.input, value=new_state))

    def on_mode_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            mode = model[tree_iter][0]
            self.input.set_mode(mode)

    def build(self) -> Gtk.Box:
        """
        Build the input view
        """
        grid = Gtk.Grid()
        grid.set_margin_bottom(10)

        label_name = Gtk.Label(label=self.input.description)
        label_name.wrap = True
        label_name.set_halign(Gtk.Align.START)
        label_name.set_hexpand(True)
        grid.attach(label_name, 0, 0, 1, 1)

        active = Gtk.CheckButton(label="Active")
        active.set_action_name("app." + self.active.get_name())
        grid.attach(active, 0, 1, 1, 1)

        if len(self.modes) > 1:
            modes = Gtk.ComboBox(model=self.modes)
            modes.set_id_column(0)
            renderer = Gtk.CellRendererText()
            modes.pack_start(renderer, True)
            modes.add_attribute(renderer, "text", 1)
            modes.set_active_id("default")
            modes.connect("changed", self.on_mode_changed)
            grid.attach(modes, 0, 2, 1, 1)

        return grid
