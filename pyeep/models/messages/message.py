import time as tm
import logging
from typing import Any, Annotated

import pydantic

from pyeep.models.primitive import Primitive

log = logging.getLogger(__name__)


class Message(Primitive):
    """Base for all messages exchanged in pyeep."""

    name: str = ""
    ts: Annotated[int, pydantic.Field(default_factory=tm.time_ns)] = 0
    src: str | None = None
    dst: str | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def _fill_message_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.setdefault("name", cls.__name__.lower())
        return data


class GroupMessage(Message):
    """Message targeting a group."""

    group: int
