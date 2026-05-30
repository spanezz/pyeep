from typing import Annotated

from pyeep.models.animation import ColorAnimation
from pyeep.animator import ColorAnimator
from pyeep.models.color import Color
from ..component.base import Component, check_hub
from ..component.controller import ControllerWidget
from pyeep.gtk import Gtk
from pyeep.models.primitive import PrimitiveField
from pyeep.models.messages.message import Message, GroupMessage
from .base import Output, OutputController


class SetGroupColor(GroupMessage):
    """
    Set the power of the outputs in the given group
    """

    color: Color | Annotated[ColorAnimation, PrimitiveField]


class ColorOutput(Output):
    """
    Output that can take color values
    """

    def set_color(self, color: Color):
        raise NotImplementedError(
            f"{self.__class__.__name__}.set_color not implemented"
        )


class ColorOutputController(OutputController):
    """
    Output controller for ColorOutput outputs
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.color = Gtk.ColorButton()
        self.color.connect("color-activated", self.on_color)
        self.color_animator = ColorAnimator(
            self.name, self.output.rate, self.set_animated_color
        )
        self.colors: dict[Component, Color] = {}
        self.animation_color: Color = Color(red=0, green=0, blue=0)

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
