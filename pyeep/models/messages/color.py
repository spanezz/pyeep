import logging
from typing import Annotated, Any

import pydantic

from pyeep.models.animation import AnimationPrimitive
from pyeep.models.color import Color
from pyeep.models.messages import Command
from pyeep.models.primitive import PrimitiveField

log = logging.getLogger(__name__)


def get_color_discriminator_value(v: Any) -> str | None:
    match v:
        case dict():
            if "primitive" in v:
                return "animation"
            else:
                return "color"
        case Color():
            return "color"
        case AnimationPrimitive():
            return "animation"
        case _:
            return None


class SetColor(Command):
    """
    Set the power of the outputs in the given group
    """

    color: Annotated[
        (
            Annotated[Color, pydantic.Tag("color")]
            | Annotated[
                AnimationPrimitive[Color],
                PrimitiveField,
                pydantic.Tag("animation"),
            ]
        ),
        pydantic.Discriminator(get_color_discriminator_value),
    ]
