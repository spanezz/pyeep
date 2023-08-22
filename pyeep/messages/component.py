from __future__ import annotations

import logging
from typing import Any

from .message import Message

log = logging.getLogger(__name__)


class Shutdown(Message):
    """
    Message sent to initiate component shutdown
    """
    pass


class NewComponent(Message):
    """
    Notify that a new component has been added
    """
    def __str__(self) -> str:
        return super().__str__() + f"(component={self.src})"


class ComponentActiveStateChanged(Message):
    """
    Notify a change of active state for an input
    """
    def __init__(self, *, value: bool, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    def __str__(self) -> str:
        return super().__str__() + f"(value={self.value})"


class DeviceScanRequest(Message):
    """
    Request to scan for new devices
    """
    def __init__(self, *, duration: float, **kwargs):
        super().__init__(**kwargs)
        # Duration in seconds of the scan
        self.duration = duration

    def __str__(self):
        return super().__str__() + f"(duration={self.duration})"
