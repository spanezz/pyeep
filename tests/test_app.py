import asyncio
import unittest
from unittest import mock
from typing import override

from pyeep.app.base import BaseApp, AppShutdownEvent


class ConcreteBaseApp(BaseApp):
    """Concrete version of BaseApp."""

    @override
    async def start_main_tasks(self) -> None:
        pass


class TestApp(unittest.IsolatedAsyncioTestCase):
    async def test_app_shutdown(self):
        self.enterContext(mock.patch("sys.argv", ["concretebaseapp"]))
        app = ConcreteBaseApp(name="test", handle_sigterm_sigint=False)
        with self.assertLogs(logger=app.log, level="INFO") as lg:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(app.main())
                await app.main_event_queue.put(AppShutdownEvent("testing quit"))

        self.assertEqual(
            lg.output, ["INFO:app.test:App shutdown: testing quit"]
        )
