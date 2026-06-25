from pyeep.models.messages import Event


class GestureEvent(Event):
    """Event notifying of a gesture."""

    #: Duration of the gesture in seconds
    duration: float


class GestureYes(GestureEvent):
    """
    A 'yes' gesture.

    This means a vertical head swing from top to bottom.
    """

    #: Gesture speed in degrees per second
    speed: float


class GestureNo(GestureEvent):
    """
    A 'no' gesture.

    This means a horizontal head swing in any direction.
    """

    #: Gesture speed in degrees per second
    speed: float
