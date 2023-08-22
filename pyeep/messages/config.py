from __future__ import annotations

import logging
from typing import Any
from .message import Message

log = logging.getLogger(__name__)


class ConfigSaveRequest(Message):
    """
    Message sent to initiate saving configuration
    """
    pass


class Configure(Message):
    """
    Message sent to a component to restore its configuration
    """
    def __init__(self, *, config: dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def __str__(self):
        return super().__str__() + f"(config={self.config!r})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["config"] = self.config
        return res
