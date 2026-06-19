import abc
import logging
from typing import override

from pyeep.models.color import Color
from pyeep.models.primitive import Primitive

log = logging.getLogger(__name__)


class Animation[T](abc.ABC):
    """Base class for animation routines."""

    @abc.abstractmethod
    def value(self, time_ns: int) -> T | None:
        """Return the value at time time_ns from animation start."""


class AnimationPrimitive[T](Primitive, abc.ABC):
    """Description of an animation."""

    @abc.abstractmethod
    def get_animation(self) -> Animation[T]:
        """Get the Animation object that computes this animation."""


class Animations[T](Animation[T]):
    """Group of animations running together."""

    def __init__(self, zero: T) -> None:
        """
        Initialize the animations group.

        :param zero: value to return when no animation has started yet
        """
        self.zero = zero
        self.animations: list[tuple[int, Animation[T]]] = []

    def add(self, start_time_ns: int, animation: Animation[T]) -> None:
        """Add an animation, to start at the given animation time."""
        self.animations.append((start_time_ns, animation))
        self.animations.sort(key=lambda x: (x[0], id(x[1])))

    @override
    def value(self, time_ns: int) -> T | None:
        if not self.animations:
            return None

        value = self.zero
        i = 0
        while i < len(self.animations):
            start, animation = self.animations[i]
            if time_ns < start:
                break

            if (a_value := animation.value(time_ns - start)) is None:
                self.animations.pop(i)
            else:
                i += 1
                value += a_value

        return value


class PowerAnimations(Animations[float]):
    def __init__(self) -> None:
        super().__init__(zero=0.0)


class ColorAnimations(Animations[Color]):
    def __init__(self) -> None:
        super().__init__(zero=Color())


class ConstAnimation[T](Animation[T]):
    """Animation for Const."""

    def __init__(self, value: "Const[T]") -> None:
        self.duration_ns = value.duration_ns
        self.const_value = value.value

    @override
    def value(self, time_ns: int) -> T | None:
        if time_ns >= self.duration_ns:
            return None
        return self.const_value


class Const[T](AnimationPrimitive[T]):
    """Animation with a constant value."""

    #: Constant value to use
    value: T
    #: Duration of the pulse
    duration_ns: int

    @override
    def get_animation(self) -> ConstAnimation[T]:
        return ConstAnimation(self)


class PowerPulseAnimation(Animation[float]):
    """Animation for PowerPulse."""

    def __init__(self, value: "PowerPulse") -> None:
        self.power = value.power
        self.duration_ns = value.duration_ns
        self.midpoint = self.duration_ns / 2

    @override
    def value(self, time_ns: int) -> float | None:
        if time_ns >= self.duration_ns:
            return None

        if time_ns < self.midpoint:
            return self.power * time_ns / self.midpoint
        else:
            return self.power * (self.duration_ns - time_ns) / self.midpoint


class PowerPulse(AnimationPrimitive[float]):
    """Pulse the power up and down again."""

    #: Amount to pulse up
    power: float
    #: Duration of the pulse
    duration_ns: int

    @override
    def get_animation(self) -> PowerPulseAnimation:
        return PowerPulseAnimation(self)


class ColorPulseAnimation(Animation[float]):
    """Animation for ColorPulse."""

    def __init__(self, value: "ColorPulse") -> None:
        self.color = value.color
        self.duration_ns = value.duration_ns
        self.midpoint = self.duration_ns / 2

    @override
    def value(self, time_ns: int) -> Color | None:
        if time_ns >= self.duration_ns:
            return None

        if time_ns < self.midpoint:
            return self.color * (time_ns / self.midpoint)
        else:
            return self.color * ((self.duration_ns - time_ns) / self.midpoint)


class ColorPulse(AnimationPrimitive[Color]):
    """Temporarily add the color to the current color."""

    #: Color to add
    color: Color
    #: Duration of the pulse
    duration_ns: int

    @override
    def get_animation(self) -> ColorPulseAnimation:
        return ColorPulseAnimation(self)


class ColorHeartPulseAnimation(Animation[float]):
    """Animation for ColorHeartPulse."""

    # TODO: refactor as an animation sequence of two color pulses

    def __init__(self, value: "ColorHeartPulse") -> None:
        self.color = value.color
        self.duration_ns = value.duration_ns
        self.atrial_duration_ns = round(
            self.duration_ns * value.atrial_duration_ratio
        )

    @override
    def value(self, time_ns: int) -> Color | None:
        if time_ns >= self.duration_ns:
            return None

        # See https://www.nhlbi.nih.gov/health/heart/heart-beats
        if time_ns < self.atrial_duration_ns:
            duration_ns = self.atrial_duration_ns
            brightness = 0.5
        else:
            time_ns -= self.atrial_duration_ns
            duration_ns = self.duration_ns - self.atrial_duration_ns
            brightness = 1.0

        midpoint = duration_ns / 2
        if time_ns < midpoint:
            return self.color * (brightness * time_ns / midpoint)
        else:
            return self.color * (
                brightness * (duration_ns - time_ns) / midpoint
            )


class ColorHeartPulse(AnimationPrimitive[Color]):
    """Heartbeat-style color pulse."""

    #: Color to add
    color: Color
    #: Duration of the pulse
    duration_ns: int
    #: Ratio of the duration used for the atrial pulse
    atrial_duration_ratio: float = 0

    @override
    def get_animation(self) -> PowerPulseAnimation:
        # TODO: return an Animations with two consecutive color pulses
        return ColorHeartPulseAnimation(self)
