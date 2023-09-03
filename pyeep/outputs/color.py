from __future__ import annotations

from ..animation import ColorAnimation, ColorAnimator
from ..color import Color
from ..component.base import Component, check_hub
from ..component.controller import ControllerWidget
from ..gtk import Gtk
from ..messages.message import Message
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
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.color = Gtk.ColorButton()
        self.color.connect("color-activated", self.on_color)
        self.color_animator = ColorAnimator(self.name, self.output.rate, self.set_animated_color)
        self.colors: dict[Component, Color] = {}
        self.animation_color: Color = Color(0, 0, 0)

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case SetGroupColor():
                if self.in_group(msg.group):
                    match msg.color:
                        case Color():
                            self.colors[msg.src] = msg.color
                            self.update_color()
                        case ColorAnimation():
                            self.color_animator.start(msg.color)
            case _:
                super().receive(msg)

    def update_color(self):
        color = self.animation_color
        if self.colors:
            color = sum(self.colors.values(), start=color)
        self.output.set_color(color)
        self.color.set_rgba(color.as_rgba())

    def on_color(self, color):
        rgba = color.get_rgba()
        self.colors[self] = Color(rgba.red, rgba.green, rgba.blue)
        self.update_color()

    def set_animated_color(self, color: Color):
        self.animation_color = color
        self.update_color()

    def build(self) -> ControllerWidget:
        cw = super().build()
        cw.toolbar.append(self.color)
        return cw
