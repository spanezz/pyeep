import json
import logging
import time as tm
from functools import cached_property
from typing import Annotated

import pydantic

from pyeep.models.primitive import Primitive

from .routing import RoutingKey, RoutingKeys

log = logging.getLogger(__name__)


class Message(Primitive):
    """Base for all messages exchanged in pyeep."""

    model_config = pydantic.ConfigDict(frozen=True)

    ts: Annotated[int, pydantic.Field(default_factory=tm.time_ns)] = 0
    src: RoutingKey | None = None

    @cached_property
    def as_json(self) -> str:
        """Serialize the message as json."""
        return json.dumps(self.model_dump())


class Event(Message):
    """
    Notify an event that happened in a component.

    This type of messages travels only upwards towards the hub, to be processed
    by scenes.
    """


class Broadcast(Message):
    """Message sent to all connected components."""


class Command(Message):
    """Command sent to one component."""

    dst: RoutingKeys
