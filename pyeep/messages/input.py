from __future__ import annotations

import logging
from typing import Any

from .message import Message

log = logging.getLogger(__name__)


class EmergencyStop(Message):
    """
    Request to stop any activity as soon as possible
    """
    pass


class Shortcut(Message):
    """
    Event notifying the trigger of a named keyboard shortcut
    """
    def __init__(self, *, command: str, **kwargs):
        super().__init__(**kwargs)
        self.command = command

    def __str__(self):
        return super().__str__() + f"(command={self.command})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["command"] = self.command
        return res


class Pause(Message):
    """
    Pause outputs in a group
    """
    def __init__(self, *, group: int, **kwargs):
        super().__init__(**kwargs)
        self.group = group

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["group"] = self.group
        return res


class Resume(Message):
    """
    Unpause outputs in a group
    """
    def __init__(self, *, group: int, **kwargs):
        super().__init__(**kwargs)
        self.group = group

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["group"] = self.group
        return res
