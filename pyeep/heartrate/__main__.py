import asyncio
import argparse
import logging
from typing import override

import rich

from pyeep.app.client import ClientApp
from pyeep.models.messages import Message
from .messages import HeartBeat

from .heartrate import HeartRateMonitor


class Heartrate(ClientApp):
    """Inspect the pyeep system."""

    def __init__(self, *, handle_sigterm_sigint: bool = True) -> None:
        super().__init__(
            name="heartrate", handle_sigterm_sigint=handle_sigterm_sigint
        )
        self.monitor = HeartRateMonitor(
            device=self.args.addr, log=logging.getLogger(f"{self.name}.ble")
        )

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    async def send_beats(self) -> None:
        async for sample in self.monitor.samples():
            print("Sample", sample)
            await self.send(HeartBeat(sample=sample))

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        tg.create_task(self.monitor.main())
        tg.create_task(self.send_beats())


if __name__ == "__main__":
    Heartrate.run()
