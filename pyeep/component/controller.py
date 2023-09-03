from __future__ import annotations

import functools
from typing import Generic, Type, TypeVar

from ..gtk import Gtk
from .base import Component
from .gtk import GtkComponent

C = TypeVar("C", bound=Component)


class ControllerWidget(Gtk.Frame):
    def __init__(self, *, label: str):
        super().__init__(label=label)

        # Stop using the frame label
        label = self.get_label_widget()
        self.set_label_widget(None)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.box)

        # Put a CenterBox at the top of the frame instead
        self.header = Gtk.CenterBox()
        self.box.append(self.header)

        # Label at the center of the header
        self.header.set_center_widget(label)

        self.set_margin_bottom(10)

    @functools.cached_property
    def toolbar(self):
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toolbar.set_hexpand(True)
        self.box.append(toolbar)
        return toolbar


class Controller(Generic[C], GtkComponent):
    def __init__(self, *, component: C, **kwargs):
        super().__init__(**kwargs)
        self.component = component

    def get_widget_class(self) -> Type[ControllerWidget]:
        return ControllerWidget

    def build(self) -> ControllerWidget:
        return self.get_widget_class()(label=self.component.description)
