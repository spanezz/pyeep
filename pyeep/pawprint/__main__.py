import argparse
import logging
import time as tm
from typing import Unpack, override

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import BaseAppArgs
from pyeep.models.messages import Event

from . import pawprint
from .pawprint import Pawprint


# from .messages import HeartBeat, Sample


class Pawprints(ApplicationAsyncCmdClientApp):
    """Interface with a DG-Lab Pawprint device."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.pawprint: Pawprint | None = None
        if self.args.addr:
            self.pawprint = Pawprint(
                self,
                device=self.args.addr,
                log=logging.getLogger(f"{self.name}.ble"),
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

    @override
    async def init(self) -> None:
        await super().init()
        if self.pawprint is not None:
            await self.start_task(self.pawprint.main())

    @override
    async def send_event(self, msg: Event) -> None:
        self.log.info("Sending event %s", msg)
        await super().send_event(msg)

    async def cmd_color(self, color: str) -> None:
        """
        Set the identification color.

        Valid values: yellow, red, violet, blue, cyan, green
        """
        if not self.pawprint:
            self.log.error("pawprint not connected")
            return
        await self.pawprint.set_color(pawprint.Color[color.upper()])

    async def cmd_start(self) -> None:
        """Start streaming data."""
        if not self.pawprint:
            self.log.error("pawprint not connected")
            return
        await self.pawprint.set_stream(True)

    async def cmd_stop(self) -> None:
        """Stop streaming data."""
        if not self.pawprint:
            self.log.error("pawprint not connected")
            return
        await self.pawprint.set_stream(False)


if __name__ == "__main__":
    Pawprints.run()
