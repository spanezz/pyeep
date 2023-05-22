from __future__ import annotations

import functools
from typing import TYPE_CHECKING
from .base import Component

if TYPE_CHECKING:
    from ..gtk import Gtk, GtkHub


class GtkComponent(Component):
    HUB = "gtk"

    def __init__(self, *, hub: "GtkHub", **kwargs):
        super().__init__(hub=hub, **kwargs)
        self.hub: "GtkHub"

    @functools.cached_property
    def widget(self) -> Gtk.Widget:
        """
        Return the widget to control this component
        """
        return self.build()

    def build(self) -> Gtk.Widget:
        """
        Build the widget to control this component
        """
        raise NotImplementedError(f"{self.__class__.__name__}.build not implemented")
