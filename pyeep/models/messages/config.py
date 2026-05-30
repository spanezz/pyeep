import logging
from typing import Any

from pyeep.models.messages.message import Message

log = logging.getLogger(__name__)


class ConfigSaveRequest(Message):
    """Message sent to initiate saving configuration."""


class Configure(Message):
    """
    Message sent to a component to restore its configuration
    """

    config: dict[str, Any]
