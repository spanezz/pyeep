from functools import cached_property
import json
import time as tm
import logging
from typing import Any, Annotated

import pydantic

from pyeep.models.primitive import Primitive

log = logging.getLogger(__name__)


class Message(Primitive):
    """Base for all messages exchanged in pyeep."""

    model_config = pydantic.ConfigDict(frozen=True)

    name: str = ""
    ts: Annotated[int, pydantic.Field(default_factory=tm.time_ns)] = 0
    src: tuple[str, ...] | None = None
    dst: str | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def _fill_message_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.setdefault("name", cls.__name__.lower())
        return data

    @cached_property
    def as_json(self) -> str:
        """Serialize the message as json."""
        return json.dumps(self.model_dump())


class GroupMessage(Message):
    """Message targeting a group."""

    group: int
