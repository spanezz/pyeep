import asyncio
import logging
import time as tm
from typing import AsyncGenerator

log = logging.getLogger(__name__)


async def beat_timer(interval_ns: int) -> AsyncGenerator[int]:
    """
    Generate a value every ``interval_ns``.

    Timer is driftless, overruns are logged and missing steps are skipped while
    trying to stick to the beat.

    Generates the number of ticks passed since the last element. This will be
    1, or 1 plus the number of ticks skipped in case of overruns.

    :param interval_ns: interval in nanoseconds between ticks
    """
    last_ns = tm.monotonic_ns()
    while True:
        next_ns = last_ns + interval_ns
        now_ns = tm.monotonic_ns()
        skipped: int = 1
        while next_ns < now_ns:
            next_ns += interval_ns
            skipped += 1
        await asyncio.sleep((next_ns - now_ns) / 1_000_000_000)
        yield skipped
        last_ns = next_ns
