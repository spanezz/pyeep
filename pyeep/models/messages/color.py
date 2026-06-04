import logging
from typing import Annotated

from pyeep.models.primitive import PrimitiveField
from pyeep.models.messages.message import GroupMessage
from pyeep.models.animation import ColorAnimation
from pyeep.models.color import Color


log = logging.getLogger(__name__)


class SetGroupColor(GroupMessage):
    """
    Set the power of the outputs in the given group
    """

    color: Color | Annotated[ColorAnimation, PrimitiveField]
