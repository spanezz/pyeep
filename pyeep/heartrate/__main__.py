import argparse
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
        self.monitor = HeartRateMonitor(
            name="monitor", device=self.args.addr, hub=self
        )

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr",
            "-a",
            required=True,
            type=str,
            help="Bluetooth address of the device",
        )
        return parser

    async def send_beats(self) -> None:
        last_rate: float | None = None
        assert self.monitor is not None
        async for sample in self.monitor.samples():
            if last_rate is None or last_rate != sample.rate:
                self.log.info("New rate: %f", sample.rate)
                last_rate = sample.rate
            await self.send_event(HeartBeat(sample=sample))

    @override
    async def init(self) -> None:
        await super().init()
        await self.add_component(self.monitor)
        await self.start_task(self.send_beats())

    async def cmd_rate(self, rate: float) -> None:
        """Simulate a heartrate report of a float rate."""
        await self.send_event(
            HeartBeat(sample=Sample(time=tm.time_ns(), rate=rate))
        )


if __name__ == "__main__":
    Heartrate.run()
