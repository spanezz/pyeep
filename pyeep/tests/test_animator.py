import asyncio
import unittest
from unittest import mock
from typing import AsyncGenerator

from pyeep.animator import PowerAnimator
from pyeep.models.animation import Const


class TestAnimator(unittest.IsolatedAsyncioTestCase):
    async def test_stop_start(self) -> None:
        invocations: int = 0
        timer_ticks: int = 0
        timer_done = asyncio.Event()

        async def mock_timer(interval_ns: int) -> AsyncGenerator[int]:
            nonlocal timer_ticks, invocations
            invocations += 1
            try:
                while True:
                    yield 1
                    timer_ticks += 1
            finally:
                timer_done.set()

        self.enterContext(
            mock.patch("pyeep.animator.beat_timer", side_effect=mock_timer)
        )

        animator = PowerAnimator("test", 1)
        generated: list[float] = []
        async with asyncio.TaskGroup() as tg:

            async def read_values() -> None:
                async for value in animator.values():
                    generated.append(value)

            read_task = tg.create_task(read_values())

            animator.add_at_next_tick(
                Const(value=1.0, duration_ns=3).get_animation()
            )
            await timer_done.wait()
            timer_done.clear()
            animator.add_at_next_tick(
                Const(value=2.0, duration_ns=3).get_animation()
            )
            await timer_done.wait()
            read_task.cancel()

        self.assertEqual(
            generated, [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 2.0, 2.0, 2.0, 0.0]
        )
        self.assertEqual(invocations, 2)
        self.assertEqual(timer_ticks, 8)
