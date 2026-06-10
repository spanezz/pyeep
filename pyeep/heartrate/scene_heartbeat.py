import asyncio
from typing import override
from pyeep.models.color import Color

from pyeep.models import animation
from pyeep.models.messages.message import Message
from pyeep.models.messages.color import SetGroupColor
from pyeep.component.component import Component
from .messages import HeartBeat


class SceneHeartbeat(Component):
    def __init__(self, *, name: str = "scene_heartbeat") -> None:
        super().__init__(name=name)
        self.timeout: int | None = None
        self.last_rate: float | None = None
        self.has_rate = asyncio.Event()
        self.group: int = 1
        self.atrial_duration_ratio = 0.2
        # self.atrial_duration_ratio = Gtk.Adjustment(
        #     lower=0.0,
        #     upper=1.0,
        #     step_increment=0.1,
        #     page_increment=0.2,
        #     value=0.2,
        # )

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case HeartBeat():
                self.last_rate = msg.sample.rate
                self.has_rate.set()

    async def tick(self) -> None:
        await self.has_rate.wait()
        assert self.last_rate is not None
        while True:
            await self.send(
                SetGroupColor(
                    group=self.group,
                    color=animation.ColorHeartPulse(
                        color=Color(red=0.5, green=0, blue=0),
                        duration_ns=round(
                            0.9 * 60 / self.last_rate * 1_000_000_000
                        ),
                        atrial_duration_ratio=self.atrial_duration_ratio,
                    ),
                )
            )
            await asyncio.sleep(60 / self.last_rate)


#    @check_hub
#    def set_active(self, value: bool) -> None:
#        super().set_active(value)
#        if not value:
#            if self.timeout is not None:
#                GLib.source_remove(self.timeout)
#                self.timeout = None
#
#    def build(self) -> Gtk.Expander:
#        expander = super().build()
#        grid = SceneGrid(max_column=self.ui_grid_columns)
#        expander.set_child(grid)
#        row = grid.max_row
#
#        grid.attach(
#            Gtk.Label(label="Ratio of atrial animation"),
#            0,
#            row,
#            self.ui_grid_columns - 1,
#            1,
#        )
#
#        spinbutton = Gtk.SpinButton()
#        spinbutton.set_adjustment(self.atrial_duration_ratio)
#        spinbutton.set_digits(1)
#        grid.attach(spinbutton, self.ui_grid_columns - 1, row, 1, 1)
#
#        return expander
#
#    def _check_timeout(self) -> None:
#        if self.last_rate is None:
#            return
#
#        if self.timeout is not None:
#            return
#
#        self.timeout = GLib.timeout_add(60 / self.last_rate * 1000, self._tick)
#
#    def _tick(self) -> bool:
#        if self.last_rate is None:
#            return False
#
#        self.send(
#            SetGroupColor(
#                group=self.get_group(),
#                color=animation.ColorHeartPulse(
#                    color=Color(red=0.5, green=0, blue=0),
#                    duration=0.9 * 60 / self.last_rate,
#                    atrial_duration_ratio=self.atrial_duration_ratio.get_value(),
#                ),
#            )
#        )
#
#        self.timeout = GLib.timeout_add(60 / self.last_rate * 1000, self._tick)
#        return False
#
#    @check_hub
#    def receive(self, msg: Message) -> None:
#        if not self.is_active:
#            return
#        match msg:
#            case HeartBeat():
#                self.last_rate = msg.sample.rate
#                self._check_timeout()
