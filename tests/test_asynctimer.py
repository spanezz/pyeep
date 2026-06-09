import asyncio
import unittest
import time as tm

from pyeep.utils.asynctimer import beat_timer


class TestTimer(unittest.IsolatedAsyncioTestCase):
    async def test_ticks(self) -> None:
        count = 0
        start = tm.monotonic_ns()
        async for steps in beat_timer(2_000_000):
            end = tm.monotonic_ns()
            count += 1
            self.assertEqual(steps, 1)
            if count == 3:
                break

        elapsed = end - start
        self.assertGreaterEqual(elapsed, 2_000_000 * 3)
        self.assertLess(elapsed, 2_000_000 * 4)

    async def test_ticks_beat_overrun(self) -> None:
        count = 0
        start = tm.monotonic_ns()
        steps_list: list[int] = []
        async for steps in beat_timer(2_000_000):
            end = tm.monotonic_ns()
            count += 1
            steps_list.append(steps)
            # TODO: this depends on system speed and load: redo the test with
            # mocking of timers to make it deterministic
            await asyncio.sleep(0.0019)
            if count == 3:
                break

        self.assertEqual(steps_list, [1, 2, 2])
        elapsed = end - start
        self.assertGreaterEqual(elapsed, 2_000_000 * 5)
        self.assertLess(elapsed, 2_000_000 * 6)
