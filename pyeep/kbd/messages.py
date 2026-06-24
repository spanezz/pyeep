from typing import Literal

from pyeep.models.messages import Event


class KeyEvent(Event):
    """Report a keystroke on a named key."""

    #: Key name
    key: str
    #: Action
    action: Literal["up", "down"]
