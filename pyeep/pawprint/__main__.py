import argparse
from typing import Unpack, override

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.models.messages.buttons import ButtonEvent
from pyeep.app.base import BaseAppArgs
from pyeep.models.messages import Event

from . import pawprint
from .pawprint import Pawprint


class Pawprints(ApplicationAsyncCmdClientApp):
    """Interface with a DG-Lab Pawprint device."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.pawprint = Pawprint(
            name="pawprint",
            device=self.args.addr,
            hub=self,
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

    @override
    async def init(self) -> None:
        await super().init()
        await self.add_component(self.pawprint)

    @override
    async def send_event(self, msg: Event) -> None:
        if isinstance(msg, ButtonEvent):
            self.log.info("Sending event %s", msg)
        await super().send_event(msg)

    async def cmd_color(self, color: str) -> None:
        """
        Set the identification color.

        Valid values: yellow, red, violet, blue, cyan, green
        """
        await self.pawprint.set_color(pawprint.Color[color.upper()])

    async def cmd_start(self) -> None:
        """Start streaming data."""
        await self.pawprint.set_stream(True)

    async def cmd_stop(self) -> None:
        """Stop streaming data."""
        if not self.pawprint:
            self.log.error("pawprint not connected")
            return
        await self.pawprint.set_stream(False)


if __name__ == "__main__":
    Pawprints.run()
