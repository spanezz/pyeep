from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .jsonable import Jsonable

if TYPE_CHECKING:
    from .component.base import Component

log = logging.getLogger(__name__)


class Message(Jsonable):
    """
    Base class for messages sent between components
    """
    def __init__(
            self, *,
            ts: float | None = None,
            src: Component | None = None,
            dst: str | None = None,
            name: str | None = None):
        self.ts = ts
        self.src = src
        self.dst = dst
        if name is None:
            self.name = self.__class__.__name__.lower()
        else:
            self.name = name

    def __str__(self) -> str:
        return self.name

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["ts"] = self.ts
        res["src"] = self.src.name if self.src else None
        res["dst"] = self.dst
        res["name"] = self.name
        return res
