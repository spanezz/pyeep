import asyncio
import argparse
import logging
from typing import override

import rich

from pyeep.app.client import ClientApp
from pyeep.component.component import Component
from pyeep.models.messages import Message
from .messages import HeartBeat

from .heartrate import HeartRateMonitor


class Heartrate(ClientApp):
    """Inspect the pyeep system."""

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    async def async_main(self) -> None:
        monitor = HeartRateMonitor(
            device=self.args.addr, log=logging.getLogger("heartrate")
        )
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.webclient.connect())
            tg.create_task(monitor.main())
            async for sample in monitor.samples():
                await self.webclient.send(HeartBeat(sample=sample))

    @override
    def main_loop(self) -> None:
        """
        Main loop.

        The application will shut down after this function returns.
        """
        try:
            asyncio.run(self.async_main())
        except KeyboardInterrupt:
            pass


Heartrate.run()
