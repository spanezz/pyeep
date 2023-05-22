from __future__ import annotations

from typing import Generic, Type, TypeVar

from ..gtk import Gtk
from .gtk import GtkComponent
from .base import Component

C = TypeVar("C", bound=Component)


class ControllerWidget(Gtk.Frame):
    def __init__(self, *, label: str):
        super().__init__(label=label)

        # Stop using the frame label
        label = self.get_label_widget()
        self.set_label_widget(None)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(box)

        # Put a CenterBox at the top of the frame instead
        self.header = Gtk.CenterBox()
        box.append(self.header)

        # The main body of the frame is a Grid
        self.grid = Gtk.Grid()
        box.append(self.grid)

        # Label at the center of the header
        self.header.set_center_widget(label)

        self.set_margin_bottom(10)


class Controller(Generic[C], GtkComponent):
    def __init__(self, *, component: C, **kwargs):
        super().__init__(**kwargs)
        self.component = component

    def get_widget_class(self) -> Type[ControllerWidget]:
        return ControllerWidget

    def build(self) -> ControllerWidget:
        return self.get_widget_class()(label=self.component.description)
