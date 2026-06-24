from typing import Literal

from pyeep.models.messages import Event


class ButtonEvent(Event):
    """Report a press or release on a named button."""

    #: Key name
    key: str
    #: Action
    action: Literal["up", "down"]
