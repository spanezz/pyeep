import asyncio
import operator
import time as tm
from typing import NamedTuple, Unpack, override

import numpy as np

from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.models.scene import SingleTargetSceneDescription
from pyeep.models.messages.gestures import GestureYes, GestureNo
from pyeep.muse.messages import HeadYesNo
from pyeep.nodes.scene import SceneArgs
from pyeep.scenes.base import WebSceneSingleTarget
from pyeep.utils.asynctimer import beat_timer


class Description(SingleTargetSceneDescription):
    """Consent scene description."""


class GestureInfo(NamedTuple):
    """Behaviour of a gesture."""

    #: Gesture name
    name: str
    #: Streak color (at maximum intensity)
    color: Color
    #: Degrees per second considered maximum gesture intensity
    max_intensity_dps: float
    #: Factor to use to multiply computed intensity before adding it to the
    #: power output
    power_intensity_factor: float
    #: Power decay, per second
    power_decay: float
    #: Color intensity decay, per second
    color_decay: float


# Behaviour for known gestures
GESTURE_YES = GestureInfo(
    name="yes",
    color=Color(red=0, green=1, blue=0),
    max_intensity_dps=600.0,
    power_intensity_factor=1,
    power_decay=0.05,
    color_decay=0.05,
)
GESTURE_NO = GestureInfo(
    name="no",
    color=Color(red=1, green=0, blue=0),
    max_intensity_dps=600.0,
    power_intensity_factor=-0.3,
    power_decay=0.05,
    color_decay=0.05,
)


@Description.scene
class SceneConsent(WebSceneSingleTarget[Description]):
    """Pulse lights red/yellow/green based on head yes/no movements."""

    def __init__(self, **kwargs: Unpack[SceneArgs[Description]]) -> None:
        super().__init__(**kwargs)

        #: Current gesture
        self.gesture: GestureInfo | None = None

        #: Computed output value for power
        self.power_output: float = 0.0

        #: Computed output value for color intensity
        self.color_output: float = 0.0

        #: If True, stop everything as soon as a "no" is detected
        # TODO: configure via UI
        self.instant_no: bool = False

        #: Power/color generation task
        self.animate_task: asyncio.Task[None] | None = None

    def reset_gesture(self) -> None:
        """Reset gesture information."""
        self.gesture = None
        self.power_output = 0.0
        self.color_output = 0.0

    async def start_animator(self) -> None:
        """Start the animator task, if it is not running."""
        if self.animate_task is not None:
            return
        self.animate_task = await self.start_task(self.animate_streak())

        def set_none(fut):
            self.animate_task = None

        self.animate_task.add_done_callback(set_none)

    @override
    async def receive(self, evt: Message) -> None:
        match evt:
            case GestureYes():
                await self.receive_gesture(GESTURE_YES, evt.speed)
            case GestureNo():
                await self.receive_gesture(GESTURE_NO, evt.speed)
            case _:
                await super().receive(evt)

    async def receive_gesture(self, gesture: GestureInfo, speed: float) -> None:
        """Handle a gesture event."""
        if not self.active:
            return

        if self.gesture is not gesture:
            self.color_output = 0.0
            self.gesture = gesture

        self.increment_output(speed)

        await self.start_animator()

    def increment_output(self, speed: float) -> None:
        assert self.gesture is not None

        # Deal with instant no
        if self.gesture is GESTURE_NO and self.instant_no:
            self.color_output = 1.0
            self.power_output = 0.0
            return

        # Go from degrees per second to an intensity ratio from 0 to 1, using
        # an arbitrary factor calibrated from experimentation
        intensity = abs(speed) / self.gesture.max_intensity_dps
        # self.log.info(
        #     "%s: intensity %f from speed %f and max_dps %f",
        #     self.gesture.name,
        #     intensity,
        #     speed,
        #     self.gesture.max_intensity_dps,
        # )
        if intensity > 1.0:
            intensity = 1.0

        self.color_output += intensity
        self.power_output += intensity * self.gesture.power_intensity_factor
        # self.log.info(
        #     "Power changed by %f * %f = %f → %f",
        #     intensity,
        #     self.gesture.power_intensity_factor,
        #     intensity * self.gesture.power_intensity_factor,
        #     self.power_output,
        # )
        self.color_output = np.clip(self.color_output, 0, 1)
        self.power_output = np.clip(self.power_output, 0, 1)
        # self.log.info(
        #     "→ color %f power %f", self.color_output, self.power_output
        # )

    async def animate_streak(self) -> None:
        """
        Animate the current streak.

        Handle sending events and decaying color and power intensities.
        """
        fps: int = 24
        async for steps in beat_timer(round(1 / fps * 1_000_000_000)):
            # self.log.info(
            #     "Animator step gesture:%s po:%f co:%f",
            #     self.gesture,
            #     self.power_output,
            #     self.color_output,
            # )
            if self.gesture is None:
                break
            if self.power_output == 0.0 and self.color_output == 0.0:
                self.reset_gesture()
                break
            self.power_output -= self.gesture.power_decay / fps
            self.color_output -= self.gesture.color_decay / fps
            if self.color_output < 0.001:
                self.color_output = 0.0
            if self.power_output < 0.001:
                self.power_output = 0.0
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.set_power(self.power_output))
                tg.create_task(
                    self.set_color(
                        self.gesture.color * self.color_output,
                    )
                )

    @override
    async def main(self) -> None:
        await asyncio.Event().wait()
