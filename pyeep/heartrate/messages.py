from pyeep.models.messages import Message
from typing import NamedTuple


class Sample(NamedTuple):
    """Data from a sample reported by the heartbeat monitor."""

    # UNIX timestamp in nanoseconds
    time: int
    rate: float
    rr: tuple[float, ...] = ()


class HeartBeat(Message):
    """Heartbeat information notification event."""

    sample: Sample
