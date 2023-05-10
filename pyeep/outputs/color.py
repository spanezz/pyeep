from __future__ import annotations

from ..animation import ColorAnimation, ColorAnimator
from ..app import Message, check_hub
from ..gtk import Gtk
from ..types import Color
from .base import Output, OutputController


class SetGroupColor(Message):
    """
    Set the power of the outputs in the given group
    """
    def __init__(self, *, group: int, color: Color | ColorAnimation, **kwargs):
        super().__init__(**kwargs)
        self.group = group
        self.color = color

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group}, color={self.color}"


class ColorOutput(Output):
    """
    Output that can take color values
    """
    def set_color(self, color: Color):
        raise NotImplementedError(f"{self.__class__.__name__}.set_color not implemented")


class ColorOutputController(OutputController):
    """
    Output controller for ColorOutput outputs
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.color = Gtk.ColorButton()
        self.color.connect("color-activated", self.on_color)
        self.color_animator = ColorAnimator(self.name, self.output.rate, self.set_animated_color)

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case SetGroupColor():
                if self.in_group(msg.group):
                    match msg.color:
                        case Color():
                            self.set_color(msg.color)
                        case ColorAnimation():
                            self.color_animator.start(msg.color)
            case _:
                super().receive(msg)

    def stop_animation(self):
        self.color_animator.stop()

    def on_color(self, color):
        self.stop_animation()
        rgba = color.get_rgba()
        self.output.set_color(Color(rgba.red, rgba.green, rgba.blue))

    def set_color(self, color: Color):
        self.stop_animation()
        self.color.set_rgba(color.as_rgba())
        self.output.set_color(color)

    def set_animated_color(self, color: Color):
        self.color.set_rgba(color.as_rgba())
        self.output.set_color(color)

    def build(self) -> Gtk.Grid:
        grid = super().build()
        grid.attach(self.color, 3, 1, 1, 1)
        return grid
