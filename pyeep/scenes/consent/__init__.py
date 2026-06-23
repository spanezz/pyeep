import asyncio
import time as tm
from typing import NamedTuple, Unpack, override

import numpy as np

from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.models.scene import SingleTargetSceneDescription
from pyeep.muse.messages import HeadYesNo
from pyeep.nodes.scene import SceneArgs
from pyeep.scenes.base import WebSceneSingleTarget
from pyeep.utils.asynctimer import beat_timer


class Description(SingleTargetSceneDescription):
    """Consent scene description."""


class GestureInfo(NamedTuple):
    """Behaviour of a gesture."""

    #: Streak color (at maximum intensity)
    color: Color
    #: Degrees per second considered maximum gesture intensity
    max_intensity_dps: float
    #: Contributed power per second (can be negative)
    #: This is the maximum (or minimum, if negative) value, which is multiplied
    #: by gesture intensity
    power_per_second: float
    #: Contributed color intensity per second (can be negative)
    #: This is the maximum (or minimum, if negative) value, which is multiplied
    #: by gesture intensity
    color_per_second: float
    #: Power decay, per second
    power_decay: float
    #: Color intensity decay, per second
    color_decay: float


# Behaviour for known gestures
GESTURES = {
    "yes": GestureInfo(
        color=Color(red=0, green=1, blue=0),
        max_intensity_dps=1.0,
        power_per_second=0.2,
        color_per_second=0.2,
        power_decay=0.04,
        color_decay=0.04,
    ),
    "no": GestureInfo(
        color=Color(red=1, green=0, blue=0),
        max_intensity_dps=0.8,
        power_per_second=-0.4,
        color_per_second=0.4,
        power_decay=0.07,
        color_decay=0.07,
    ),
    "meh": GestureInfo(
        color=Color(red=1, green=1, blue=0),
        max_intensity_dps=0.5,
        power_per_second=-0.1,
        color_per_second=0.2,
        power_decay=0.05,
        color_decay=0.05,
    ),
}


class SceneEvent:
    """Event for the scene event queue."""


class NewStreakEvent(SceneEvent):
    """New streak detected."""


class StreakExtendedEvent(SceneEvent):
    """Streak has been extended."""


class DecayedToZeroEvent(SceneEvent):
    """Output decayed to zero."""


@Description.scene
class SceneConsent(WebSceneSingleTarget[Description]):
    """Pulse lights red/yellow/green based on head yes/no movements."""

    def __init__(self, **kwargs: Unpack[SceneArgs[Description]]) -> None:
        super().__init__(**kwargs)

        #: Message that started the gesture streak
        self.streak_start: HeadYesNo | None = None
        #: Last message in the gesture streak
        self.streak_last: HeadYesNo | None = None

        #: Information about the current gesture
        self.gesture_info: GestureInfo | None = None

        #: Computed output value for power
        self.power_output: float = 0.0

        #: Computed output value for color intensity
        self.color_output: float = 0.0

        #: Time the output was last incremented
        self.last_increment_time: float = 0.0

        #: If True, stop everything as soon as a "no" is detected
        # TODO: configure via UI
        self.instant_no: bool = False

        #: Scene event queue
        self.event_queue: asyncio.Queue[SceneEvent] = asyncio.Queue()

        #: Power/color generation task
        self.animate_task: asyncio.Task[None] | None = None

    def reset_gesture(self) -> None:
        """Reset gesture information."""
        self.streak_start = None
        self.streak_last = None
        self.gesture_info = None
        self.power_output = 0.0
        self.color_output = 0.0
        self.last_increment_time = 0.0
        if self.animate_task is not None:
            self.animate_task.cancel()
            self.animate_task = None

    @override
    async def receive(self, msg: Message) -> None:
        assert self.streak_start is not None and self.streak_last is not None
        match msg:
            case HeadYesNo():
                if (
                    self.streak_start is None
                    or self.streak_start.gesture != msg.gesture
                    or msg.ts - self.streak_last.ts > 500_000_000
                ):
                    self.streak_start = msg
                    self.streak_last = msg
                    await self.event_queue.put(NewStreakEvent())
                else:
                    self.streak_last = msg
                    await self.event_queue.put(StreakExtendedEvent())

    async def animate_streak(self) -> None:
        """
        Animate the current streak.

        Handle sending events and decaying color and power intensities.
        """
        fps: int = 24
        async for steps in beat_timer(round(1 / fps * 1_000_000_000)):
            if self.gesture_info is None:
                break
            if self.power_output == 0.0 and self.color_output == 0.0:
                await self.event_queue.put(DecayedToZeroEvent())
                break
            self.power_output -= self.gesture_info.power_decay / fps
            self.color_output -= self.gesture_info.color_decay / fps
            if self.color_output < 0.001:
                self.color_output = 0.0
            if self.power_output < 0.001:
                self.power_output = 0.0
            await self.set_power(self.power_output)
            await self.set_color(
                self.gesture_info.color * self.color_output,
            )

    def increment_output(self) -> None:
        assert self.streak_start is not None
        assert self.streak_last is not None
        assert self.gesture_info is not None
        # in_streak = round(self.streak_last.ts - self.streak_start.ts)

        # Deal with instant no
        if self.streak_start.gesture == "no" and self.instant_no:
            self.color_output = 1.0
            self.power_output = 0.0
            return

        # Compute the time passed since the last increment
        elapsed: float
        cur_time = tm.time()
        if self.last_increment_time == 0:
            elapsed = 0.1
        else:
            elapsed = cur_time - self.last_increment_time
        self.last_increment_time = cur_time

        # Go from degrees per second to an intensity ratio from 0 to 1, using
        # an arbitrary factor calibrated from experimentation
        intensity = (
            self.streak_last.intensity / self.gesture_info.max_intensity_dps
        )
        if intensity > 1.0:
            intensity = 1.0

        self.color_output += (
            intensity * self.gesture_info.color_per_second * elapsed
        )
        self.power_output += (
            intensity * self.gesture_info.power_per_second * elapsed
        )
        self.color_output = np.clip(self.color_output, 0, 1)
        self.power_output = np.clip(self.power_output, 0, 1)

    @override
    async def main(self) -> None:
        try:
            while True:
                match await self.event_queue.get():
                    case NewStreakEvent():
                        assert self.streak_start is not None
                        try:
                            self.gesture_info = GESTURES[
                                self.streak_start.gesture
                            ]
                        except KeyError:
                            self.log.error(
                                "Unrecognized gesture %r",
                                self.streak_start.gesture,
                            )
                            # TODO: log unknown gesture name?
                            continue
                        self.color_output = 0.0
                        self.increment_output()
                        if self.animate_task is None:
                            self.animate_task = await self.start_task(
                                self.animate_streak()
                            )
                    case StreakExtendedEvent():
                        self.increment_output()
                    case DecayedToZeroEvent():
                        self.reset_gesture()
        except Exception as e:
            self.log.error("Exception %s", e, exc_info=e)
