import logging

from pyeep.models.messages.message import Message

log = logging.getLogger(__name__)


class Shutdown(Message):
    """Message sent to initiate component shutdown."""


class NewComponent(Message):
    """
    Notify that a new component has been added.

    The new component is named in ``self.src``.
    """


class ComponentActiveStateChanged(Message):
    """Notify a change of active state for an input."""

    value: bool


class DeviceScanRequest(Message):
    """Request to scan for new devices."""

    duration: float
