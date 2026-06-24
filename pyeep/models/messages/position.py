from pyeep.models.messages import Event


class OrientationEvent(Event):
    """Pitch/roll orientation."""

    pitch: float
    roll: float


class AccelerationEvent(Event):
    """Acceleration in m/s²."""

    value: float
