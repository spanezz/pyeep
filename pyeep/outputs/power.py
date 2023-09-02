from __future__ import annotations

from typing import Any, Type

from ..animation import PowerAnimation, PowerAnimator
from ..color import Color
from ..component.aio import AIOComponent
from ..component.base import Component, check_hub, export
from ..component.controller import ControllerWidget
from ..component.subprocess import BottomComponent, TopComponent
from ..gtk import GLib, Gtk
from ..messages.component import Shutdown
from ..messages.config import Configure
from ..messages.message import Message
from .base import Output, OutputController
from .color import ColorOutput, ColorOutputController


class PowerOutput(Output):
    """
    Output with a changeable power (represented as a float from 0 to 1)
    """

    def set_power(self, power: float):
        raise NotImplementedError(f"{self.__class__.__name__}.set_power not implemented")

    def get_output_controller(self) -> Type["PowerOutputController"]:
        return PowerOutputController


class PowerOutputTop(TopComponent, PowerOutput):
    """
    PowerOutput sending power commands to a subprocess
    """
    @export
    def set_power(self, power: float):
        self.forward_message(SetPower(power=power))

    async def process_remote_message(self, msg: Message):
        match msg:
            case SetRate():
                self.set_rate(msg.rate)


class PowerOutputBottom(BottomComponent):
    """
    PowerOutput forwarding power commands from a TopComponent to a PowerOutput
    """
    def __init__(self, output: PowerOutput, **kwargs):
        super().__init__(**kwargs)
        self.output = output
        self.output.add_set_rate_callback(self._notify_set_rate)

    @export
    def _notify_set_rate(self, rate: int):
        self.forward_message(SetRate(rate=rate))

    async def process_remote_message(self, msg: Message):
        match msg:
            case SetPower():
                self.output.set_power(msg.power)


class SetRate(Message):
    """
    Notify the sample rate of a component

    This is mainly used to for communication between a PowerOutputBottom and a
    PowerOutputTop
    """
    def __init__(self, *, rate: float, **kwargs):
        super().__init__(**kwargs)
        self.rate = rate

    def __str__(self) -> str:
        return super().__str__() + f"(rate={self.rate})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["rate"] = self.rate
        return res


class SetPower(Message):
    """
    Set the power of an output.

    This is mainly used to send power commands from a PowerOutputTop to a
    PowerOutputBottom
    """
    def __init__(self, *, power: float, **kwargs):
        super().__init__(**kwargs)
        self.power = power

    def __str__(self) -> str:
        return super().__str__() + f"(power={self.power})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["power"] = self.power
        return res


class SetGroupPower(Message):
    """
    Set the power of the outputs in the given group
    """
    def __init__(self, *, group: int, power: float | PowerAnimation, **kwargs):
        super().__init__(**kwargs)
        self.group = group
        self.power = power

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group}, power={self.power})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["group"] = self.group
        res["power"] = fun() if (fun := getattr(self.power, "as_jsonable", None)) else self.power
        return res


class IncreaseGroupPower(Message):
    """
    Increase the power of an output group by a given amount
    """
    def __init__(self, *, group: int, amount: float | PowerAnimation, **kwargs):
        super().__init__(**kwargs)
        self.group = group
        self.amount = amount

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group}, amount={self.amount})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["group"] = self.group
        fun = getattr(self.amount, "as_jsonable", None)
        res["amount"] = fun() if fun is not None else self.amount
        return res


class NullOutput(PowerOutput, ColorOutput, AIOComponent):
    """
    Output that does nothing besides tracking the last set power value
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("rate", 20)
        super().__init__(**kwargs)
        self.power: float = 0.0
        self.color: Color = Color()

    @property
    def description(self) -> str:
        return "Null output"

    def get_output_controller(self) -> Type[OutputController]:
        class Controller(PowerOutputController, ColorOutputController):
            pass
        return Controller

    @export
    def set_power(self, power: float):
        self.power = power

    @export
    def set_color(self, color: Color):
        self.color = color

    async def run(self):
        while True:
            msg = await self.next_message()
            match msg:
                case Shutdown():
                    break


class PowerOutputController(OutputController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.power = Gtk.Adjustment(
                value=0,
                lower=0,
                upper=100,
                step_increment=5,
                page_increment=10,
                page_size=0)
        self.power.connect("value_changed", self.on_power)

        self.power_min = Gtk.Adjustment(
                value=0,
                lower=0,
                upper=100,
                step_increment=5,
                page_increment=10,
                page_size=0)
        self.power_min.connect("value_changed", self.on_power_min)

        self.power_max = Gtk.Adjustment(
                value=100,
                lower=0,
                upper=100,
                step_increment=5,
                page_increment=10,
                page_size=0)
        self.power_max.connect("value_changed", self.on_power_max)

        self.power_animator: PowerAnimator | None = None

        self.power_levels: dict[Component, float] = {}

    # Controller/UI handlers

    @check_hub
    def on_power(self, adj):
        """
        When the Adjustment value is changed, message the output with the new
        power level
        """
        val = round(adj.get_value())
        if not self.is_paused:
            self.output.set_power(val / 100.0)

    @check_hub
    def on_power_min(self, adj):
        """
        Adjust minimum power
        """
        val = round(adj.get_value())
        self.power.set_lower(val)
        if (power := round(self.power.get_value())) < val:
            self.power.set_value(power)

    @check_hub
    def on_power_max(self, adj):
        """
        Adjust maximum power
        """
        val = round(adj.get_value())
        self.power.set_upper(val)
        if (power := round(self.power.get_value())) > val:
            self.power.set_value(power)

    @check_hub
    def on_manual_power(self, scale, scroll, value):
        """
        When the Scale value is changed, activate manual mode
        """
        self.set_manual_power(int(round(value)))

    # High-level actions

    @check_hub
    def set_source_power(self, src: Component, power: float):
        """
        Set power to use when not in manual mode and not paused
        """
        if self.is_manual:
            return
        self.power_levels[src] = power
        combined = sum(self.power_levels.values())
        self.power.set_value(round(combined * 100.0))

    @check_hub
    def set_animated_power(self, power: float):
        """
        Add to the current power the power generated by the animator
        """
        self.set_source_power(self, power)

    @check_hub
    def set_manual_power(self, power: int):
        """
        Set manual mode and maunal mode power
        """
        if not self.is_manual:
            self.manual.set_state(GLib.Variant.new_boolean(True))
        self.power.set_value(power)

    @check_hub
    def set_paused(self, paused: bool):
        """
        Enter/exit pause mode
        """
        super().set_paused(paused)

        if paused:
            self.output.set_power(0)
        else:
            power = self.power.get_value() / 100.0
            self.output.set_power(power)

    @check_hub
    def emergency_stop(self):
        self.power.set_value(0)
        self.power_levels.clear()
        super().emergency_stop()

    @check_hub
    def get_config(self) -> dict[str, Any]:
        res = super().get_config()
        res["power"] = self.power.get_value()
        return res

    @check_hub
    def load_config(self, config: dict[str, Any]):
        super().load_config(config)
        if (power := config.get("power")):
            self.power.set_value(power)

    def _start_power_animation(self, animation: PowerAnimation):
        if self.output.rate == 0:
            self.logger.warning("skipping animation %r as output rate is still unknown", animation)
            return

        if self.power_animator is None:
            self.power_animator = PowerAnimator(self.name, self.output.rate, self.set_animated_power)
        self.power_animator.start(animation)

    @check_hub
    def receive(self, msg: Message):
        match msg:
            case SetGroupPower():
                if self.in_group(msg.group):
                    self.set_source_power(msg.src, msg.power)
            case IncreaseGroupPower():
                if self.in_group(msg.group):
                    match msg.amount:
                        case PowerAnimation():
                            self._start_power_animation(msg.amount)
            case Configure():
                # TODO: forward config to the controller? Does it exist
                # yet? Change Hub to enqueue messages for not-yet-existing
                # components?
                self.load_config(msg.config)
            case _:
                super().receive(msg)

    def build(self) -> ControllerWidget:
        cw = super().build()

        power = Gtk.Scale(
                orientation=Gtk.Orientation.HORIZONTAL,
                adjustment=self.power)
        power.set_digits(2)
        power.set_draw_value(False)
        power.set_hexpand(True)
        power.connect("change-value", self.on_manual_power)
        for mark in (25, 50, 75):
            power.add_mark(
                value=mark,
                position=Gtk.PositionType.BOTTOM,
                markup=None
            )
        cw.grid.attach(power, 0, 2, 4, 1)

        power_min = Gtk.SpinButton()
        power_min.set_adjustment(self.power_min)
        cw.grid.attach(power_min, 0, 3, 1, 1)

        cw.grid.attach(Gtk.Label(label="to"), 1, 3, 2, 1)

        power_max = Gtk.SpinButton()
        power_max.set_adjustment(self.power_max)
        cw.grid.attach(power_max, 3, 3, 1, 1)

        return cw
