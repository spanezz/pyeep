from __future__ import annotations

import inspect
from typing import Iterator, NamedTuple, TypeVar

from .base import Component, export
from ..gtk import Gtk
from .controller import Controller, ControllerWidget

C = TypeVar("C", bound="ModeComponent")


class ModeInfo(NamedTuple):
    """
    Information about one input mode
    """
    name: str
    summary: str


class ModeComponent(Component):
    """
    Mixin for components to implement multiple operational modes
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_mode("default")

    def list_modes(self) -> Iterator[ModeInfo]:
        """
        List available modes
        """
        for name, value in inspect.getmembers(self, inspect.ismethod):
            if not name.startswith("mode_"):
                continue
            yield ModeInfo(name[5:], inspect.getdoc(value) or name)

    @export
    def set_mode(self, name: str) -> None:
        """
        Set the active mode
        """
        self.mode = getattr(self, "mode_" + name)


class ModeController(Controller[C]):
    """
    User interface side for an input (controller and view)
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.modes = Gtk.ListStore(str, str)
        for info in self.component.list_modes():
            self.modes.append([info.name, info.summary])

    def on_mode_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            mode = model[tree_iter][0]
            self.component.set_mode(mode)

    def build(self) -> ControllerWidget:
        """
        Build the input view
        """
        cw = super().build()

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
