import argparse
import logging
from typing import override, Unpack

from pyeep.app.base import BaseAppArgs
from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp

from . import modes
from .muse import Muse


class MuseApp(ApplicationAsyncCmdClientApp):
    """Interface with the Muse EEG monitor."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.muse: Muse | None = None
        self.mode: modes.Mode | None = None
        if self.args.addr:
            self.muse = Muse(
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
        parser.add_argument(
            "--mode", "-m", type=str, help="Mode to set at startup"
        )
        return parser

    @override
    async def start_main_tasks(self) -> None:
        await super().start_main_tasks()
        if self.muse is not None:
            await self.start_task(self.muse.main())
        if self.args.mode is not None:
            await self.set_mode(self.args.mode)

    async def set_mode(self, name: str) -> None:
        if (selected := modes.modes.get(name)) is None:
            await self.interface.print_error(f"Mode {name!r} not found.")
            return
        if self.muse is not None:
            self.mode = selected(muse=self.muse, app=self)
            await self.mode.start()

    async def cmd_mode(self, value: str) -> None:
        """Set the monitor mode, use 'list' to list modes."""
        if value == "list":
            self.interface.term.add_line([("", "Available modes:")])
            for name, mode_cls in modes.modes.items():
                if mode_cls.__doc__ is None:
                    summary = "Description not available."
                else:
                    summary = mode_cls.__doc__.strip().split("\n", 1)[0].strip()
                self.interface.term.add_line(
                    [("bold", name), ("", f": {summary}")]
                )
        else:
            await self.set_mode(value)


if __name__ == "__main__":
    MuseApp.run()
