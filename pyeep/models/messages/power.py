from typing import Annotated

from pyeep.models.animation import AnimationPrimitive
from pyeep.models.messages.message import Command
from pyeep.models.primitive import PrimitiveField


class SetPower(Command):
    """
    Set the power of an output.

    This is mainly used to send power commands from a PowerOutputTop to a
    PowerOutputBottom
    """

    power: float | Annotated[AnimationPrimitive[float], PrimitiveField]


class IncreasePower(Command):
    """Increase the power of an output by a given amount."""

    power: float | Annotated[AnimationPrimitive[float], PrimitiveField]
