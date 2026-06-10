import logging
from typing import Annotated

from pyeep.models.primitive import PrimitiveField
from pyeep.models.messages.message import Message, GroupMessage
from pyeep.models.animation import AnimationPrimitive


log = logging.getLogger(__name__)


class SetRate(Message):
    """
    Notify the sample rate of a component

    This is mainly used to for communication between a PowerOutputBottom and a
    PowerOutputTop
    """

    rate: float


class SetPower(Message):
    """
    Set the power of an output.

    This is mainly used to send power commands from a PowerOutputTop to a
    PowerOutputBottom
    """

    power: float


class SetGroupPower(GroupMessage):
    """.Set the power of the outputs in the given group."""

    power: float | Annotated[AnimationPrimitive[float], PrimitiveField]


class IncreaseGroupPower(GroupMessage):
    """Increase the power of an output group by a given amount."""

    amount: float | Annotated[AnimationPrimitive[float], PrimitiveField]
