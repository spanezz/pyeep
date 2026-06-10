import logging
from typing import Annotated, Union, Any

import pydantic

from pyeep.models.primitive import PrimitiveField
from pyeep.models.messages.message import GroupMessage
from pyeep.models.animation import AnimationPrimitive
from pyeep.models.color import Color


log = logging.getLogger(__name__)


def get_color_discriminator_value(v: Any) -> str | None:
    match v:
        case dict():
            if "py_module" in v:
                return "animation"
            else:
                return "color"
        case Color():
            return "color"
        case AnimationPrimitive():
            return "animation"
        case _:
            return None


class SetGroupColor(GroupMessage):
    """
    Set the power of the outputs in the given group
    """

    color: Annotated[
        Union[
            Annotated[Color, pydantic.Tag("color")],
            Annotated[
                AnimationPrimitive[Color],
                PrimitiveField,
                pydantic.Tag("animation"),
            ],
        ],
        pydantic.Discriminator(get_color_discriminator_value),
    ]
