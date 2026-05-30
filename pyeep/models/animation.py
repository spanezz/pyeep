import abc
import logging
import math
from collections.abc import Generator
from typing import override

from pyeep.models.primitive import Primitive
from pyeep.models.color import Color

log = logging.getLogger(__name__)


class Animation[T](Primitive, abc.ABC):
    """Base class for animation routines."""

    @abc.abstractmethod
    def values(self, rate: int) -> Generator[T]:
        """
        Generate the animation sequence.

        :param rate: frame rate in frames per second
        """


class PowerAnimation(Animation[float]):
    """Animate a power value from 0 to 1."""


class ColorAnimation(Animation[Color]):
    """Animate a Color value."""


class PowerPulse(PowerAnimation):
    """Pulse the power up and down again."""

    #: Amount to pulse up
    power: float
    #: Duration of the pulse
    duration: float

    @override
    def values(self, rate: int) -> Generator[float]:
        frame_count = math.floor(self.duration * rate)
        for frame in range(frame_count):
            envelope = (frame_count - frame) / frame_count
            yield self.power * envelope
        yield 0


class ColorPulse(ColorAnimation):
    """Temporarily add the color to the current color."""

    #: Color to add
    color: Color
    #: Duration of the pulse
    duration: float

    @override
    def values(self, rate: int) -> Generator[Color]:
        frame_count = math.floor(self.duration * rate)
        for frame in range(frame_count):
            envelope = (frame_count - frame) / frame_count
            yield Color(
                red=self.color.red * envelope,
                green=self.color.green * envelope,
                blue=self.color.blue * envelope,
            )
        yield Color(red=0, green=0, blue=0)


class ColorHeartPulse(ColorAnimation):
    """Heartbeat-style color pulse."""

    #: Color to add
    color: Color
    #: Duration of the pulse
    duration: float
    #: Ratio of the duration used for the atrial pulse
    atrial_duration_ratio: float = 0

    @override
    def values(self, rate: int) -> Generator[Color]:
        # See https://www.nhlbi.nih.gov/health/heart/heart-beats
        frame_count = math.floor(self.duration * rate)
        atrial_frames = round(frame_count * self.atrial_duration_ratio)
        ventricular_frames = frame_count - atrial_frames

        for frame in range(atrial_frames):
            envelope = 0.5 * (atrial_frames - frame) / atrial_frames
            yield Color(
                red=self.color.red * envelope,
                green=self.color.green * envelope,
                blue=self.color.blue * envelope,
            )

        for frame in range(ventricular_frames):
            envelope = (ventricular_frames - frame) / ventricular_frames
            yield Color(
                red=self.color.red * envelope,
                green=self.color.green * envelope,
                blue=self.color.blue * envelope,
            )

        yield Color(red=0, green=0, blue=0)
