from typing import NamedTuple

from pyeep.models.messages import Event


class Sample(NamedTuple):
    """Data from a sample reported by the heartbeat monitor."""

    # UNIX timestamp in nanoseconds
    time: int
    rate: float
    rr: tuple[float, ...] = ()


class HeartBeat(Event):
    """Heartbeat information notification event."""

    sample: Sample
