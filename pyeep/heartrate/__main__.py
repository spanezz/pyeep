import argparse
import logging
import time as tm
from typing import Unpack, override

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import BaseAppArgs

from .heartrate import HeartRateMonitor
from .messages import HeartBeat, Sample


class Heartrate(ApplicationAsyncCmdClientApp):
    """Inspect the pyeep system."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.monitor: HeartRateMonitor | None = None
        if self.args.addr:
            self.monitor = HeartRateMonitor(
                device=self.args.addr, log=logging.getLogger(f"{self.name}.ble")
            )

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    async def send_beats(self) -> None:
        assert self.monitor is not None
        async for sample in self.monitor.samples():
            await self.send_event(HeartBeat(sample=sample))

    @override
    async def init(self) -> None:
        await super().init()
        if self.monitor is not None:
            await self.start_task(self.monitor.main())
            await self.start_task(self.send_beats())

    async def cmd_rate(self, rate: float) -> None:
        """Simulate a heartrate report of a float rate."""
        await self.send_event(
            HeartBeat(sample=Sample(time=tm.time_ns(), rate=rate))
        )


if __name__ == "__main__":
    Heartrate.run()
