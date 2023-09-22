from __future__ import annotations

from pyeep.color import Color
from pyeep.component.base import check_hub
from pyeep.gtk import GLib
from pyeep.messages.message import Message
from pyeep.messages.input import Pause, Resume, Shortcut
from pyeep.outputs.color import SetGroupColor

from .. import animation
from ..outputs.power import IncreaseGroupPower
from .base import SingleGroupPowerScene, register


class KeyboardShortcutMixin:
    @check_hub
    def handle_keyboard_shortcut(self, shortcut: str):
        match shortcut:
            case "STOP" | "NEXT":
                self.send(Pause(group=self.get_group()))
            case "CYCLE START" | "PREVIOUS":
                self.send(Resume(group=self.get_group()))
            case "F+":
                self.increment_power(0.05)
            case "F-":
                self.increment_power(-0.05)
            case "PULSE":
                self.send(IncreaseGroupPower(
                    group=self.get_group(),
                    amount=animation.PowerPulse(power=0.3, duration=0.5)))
                self.send(SetGroupColor(
                    group=self.get_group(),
                    color=animation.ColorPulse(color=Color(1, 0, 0), duration=0.5)))
            case "SWIPE UP":
                self.increment_power(-0.05)
            case "SWIPE DOWN":
                self.increment_power(0.05)
            case "SWIPE RIGHT":
                self.increment_power(0.1)
            case "SWIPE LEFT":
                self.increment_power(-0.1)
            case "VOLUME UP":
                self.set_power(1)
            case "VOLUME DOWN":
                self.set_power(0)
            case "TAP":
                self.send(IncreaseGroupPower(
                    group=self.get_group(),
                    amount=animation.PowerPulse(power=0.3, duration=0.5)))
                self.send(SetGroupColor(
                    group=self.get_group(),
                    color=animation.ColorPulse(color=Color(1, 0, 0), duration=0.5)))


@register
class Default(KeyboardShortcutMixin, SingleGroupPowerScene):
    TITLE = "Default"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Active by default
        self.active.set_state(GLib.Variant.new_boolean(True))

    @check_hub
    def receive(self, msg: Message):
        if not self.is_active:
            return
        match msg:
            case Shortcut():
                self.handle_keyboard_shortcut(msg.command)
