import abc
import logging
from typing import override
from collections.abc import AsyncGenerator

from pyeep.models.animation import (
    Animation,
    Animations,
    PowerAnimations,
    ColorAnimations,
)
from pyeep.models.color import Color
from pyeep.utils.asynctimer import beat_timer

log = logging.getLogger(__name__)


class Animator[T](abc.ABC):
    """
    Run an animation using GLib timers, notifying each new value using a
    callback function
    """

    def __init__(self, name: str, frame_duration_ns: int) -> None:
        self.name = name
        self.frame_duration_ns = frame_duration_ns
        self.animations: Animations[T] = self.get_animations()
        self.animation_ns: int = 0

    @override
    def __str__(self) -> str:
        return f"Animator({self.name})"

    @abc.abstractmethod
    def get_animations(self) -> Animations[T]:
        """Instantiate the Animations sequence for this animator."""

    def add_at_next_tick(self, a: Animation[T]) -> None:
        """Add an animation to start at the next frame tick."""
        self.animations.add((self.animation_ns + self.frame_duration_ns), a)

    async def values(self) -> AsyncGenerator[T]:
        """Generate animation values every frame_duration_is."""
        if (value := self.animations.value(self.animation_ns)) is not None:
            yield value
        async for ticks in beat_timer(self.frame_duration_ns):
            self.animation_ns += ticks * self.frame_duration_ns
            if (value := self.animations.value(self.animation_ns)) is not None:
                yield value


class PowerAnimator(Animator[float]):
    """Animation for power sequences."""

    @override
    def get_animations(self) -> PowerAnimations:
        return PowerAnimations()


class ColorAnimator(Animator[Color]):
    """Animation for color sequences."""

    @override
    def get_animations(self) -> ColorAnimations:
        return ColorAnimations()
