import asyncio
import abc
import logging
from collections.abc import AsyncGenerator
from typing import override

from pyeep.models.animation import (
    Animation,
    Animations,
    ColorAnimations,
    PowerAnimations,
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
        self.animations: Animations[T] | None = None
        self.animation_ns: int = 0
        self.have_animations = asyncio.Event()

    @override
    def __str__(self) -> str:
        return f"Animator({self.name})"

    @property
    def running(self) -> bool:
        """Check if there are running animations."""
        return self.animations is not None

    @abc.abstractmethod
    def get_animations(self) -> Animations[T]:
        """Instantiate the Animations sequence for this animator."""

    def add_at_next_tick(self, a: Animation[T]) -> None:
        """Add an animation to start at the next frame tick."""
        notify: bool = False
        if self.animations is None:
            self.animations = self.get_animations()
            self.animations_ns = 0
            notify = True
        self.animations.add((self.animation_ns + self.frame_duration_ns), a)
        if notify:
            self.have_animations.set()

    async def values(self) -> AsyncGenerator[T]:
        """Generate animation values every frame_duration_is."""
        while True:
            await self.have_animations.wait()
            assert self.animations is not None

            if (value := self.animations.value(self.animation_ns)) is not None:
                yield value
            async for ticks in beat_timer(self.frame_duration_ns):
                self.animation_ns += ticks * self.frame_duration_ns
                if (
                    value := self.animations.value(self.animation_ns)
                ) is not None:
                    yield value
                else:
                    # When all animations have stopped, wait for more
                    self.have_animations.clear()
                    self.animations = None
                    break


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
