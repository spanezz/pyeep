from __future__ import annotations

from pyeep.color import Color
from pyeep.component.base import check_hub
from pyeep.gtk import GLib, Gtk
from pyeep.inputs.heartrate import HeartBeat
from ..messages.message import Message
from pyeep.outputs.color import SetGroupColor

from .. import animation
from .base import SceneGrid, SingleGroupScene, register


@register
class Heartbeat(SingleGroupScene):
    TITLE = "Heartbeat"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.timeout: int | None = None
        self.last_rate: int | None = None
        self.atrial_duration_ratio = Gtk.Adjustment(
                lower=0.0, upper=1.0, step_increment=0.1, page_increment=0.2, value=0.2)

    @check_hub
    def set_active(self, value: bool):
        super().set_active(value)
        if not value:
            if self.timeout is not None:
                GLib.source_remove(self.timeout)
                self.timeout = None

    def build(self) -> Gtk.Expander:
        expander = super().build()
        grid = SceneGrid(max_column=self.ui_grid_columns)
        expander.set_child(grid)
        row = grid.max_row

        grid.attach(Gtk.Label(label="Ratio of atrial animation"), 0, row, self.ui_grid_columns - 1, 1)

        spinbutton = Gtk.SpinButton()
        spinbutton.set_adjustment(self.atrial_duration_ratio)
        spinbutton.set_digits(1)
        grid.attach(spinbutton, self.ui_grid_columns - 1, row, 1, 1)

        return expander

    def _check_timeout(self):
        if self.last_rate is None:
            return

        if self.timeout is not None:
            return

        self.timeout = GLib.timeout_add(
                60 / self.last_rate * 1000,
                self._tick)

    def _tick(self):
        if self.last_rate is None:
            return False

        self.send(SetGroupColor(
            group=self.get_group(),
            color=animation.ColorHeartPulse(
                color=Color(0.5, 0, 0),
                duration=0.9 * 60 / self.last_rate,
                atrial_duration_ratio=self.atrial_duration_ratio.get_value())))

        self.timeout = GLib.timeout_add(
                60 / self.last_rate * 1000,
                self._tick)
        return False

    @check_hub
    def receive(self, msg: Message):
        if not self.is_active:
            return
        match msg:
            case HeartBeat():
                self.last_rate = msg.sample.rate
                self._check_timeout()
