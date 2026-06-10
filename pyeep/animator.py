import logging
from collections.abc import Callable, Generator

from pyeep.models.animation import Animation
from pyeep.models.color import Color
from pyeep.gtk import GLib
from pyeep.utils.asynctimer import beat_timer

log = logging.getLogger(__name__)


class Animator[T]:
    """
    Run an animation using GLib timers, notifying each new value using a
    callback function
    """

    def __init__(self, name: str, rate: int, on_value: Callable[[T], None]):
        self.name = name
        self.rate = rate
        self.timeout: int | None = None
        self.animations: set[Generator[T]] = set()
        self.on_value = on_value

    def __str__(self) -> str:
        return f"Animator({self.name})"

    def start(self, animation: Animation[T]):
        self.animations.add(animation.values(self.rate))
        if self.timeout is None:
            self.timeout = GLib.timeout_add(
                round(1 / self.rate * 1000), self.on_frame
            )

    def stop(self):
        if self.timeout is not None:
            GLib.source_remove(self.timeout)
        self.timeout = None
        self.animations = set()

    def merge(self, values: list[T]) -> T:
        raise NotImplementedError(
            f"{self.__class__.__name__}.merge not implmeented"
        )

    def on_frame(self) -> bool:
        if not self.animations:
            # All animations have finished
            self.timeout = None
            return False

        values: list[T] = []
        for a in list(self.animations):
            try:
                values.append(next(a))
            except StopIteration:
                self.animations.remove(a)

        if not values:
            # All animations have finished
            self.timeout = None
            return False

        self.on_value(self.merge(values))
        return True


class PowerAnimator(Animator[float]):
    """
    Animation for power sequences
    """

    def merge(self, values: list[float]) -> float:
        if len(values) == 1:
            return values[0]
        return sum(values, start=0.0)


class ColorAnimator(Animator[Color]):
    """
    Animation for color sequences
    """

    def merge(self, values: list[Color]) -> Color:
        if len(values) == 1:
            return values[0]
        return sum(values, start=Color(red=0, green=0, blue=0))
