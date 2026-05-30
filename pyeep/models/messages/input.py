import logging

from pyeep.models.messages.message import Message, GroupMessage

log = logging.getLogger(__name__)


class EmergencyStop(Message):
    """Request to stop any activity as soon as possible."""


class Shortcut(Message):
    """Event notifying the trigger of a named keyboard shortcut."""

    command: str


class Pause(GroupMessage):
    """Pause outputs in a group."""


class Resume(GroupMessage):
    """Unpause outputs in a group."""
