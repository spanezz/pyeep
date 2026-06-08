import asyncio
import argparse
import logging
import time as tm
from typing import override

from pyeep.app.asynccmd import ApplicationAsyncCmd, AsyncCmdQuit
from pyeep.app.base import AppShutdownEvent
from pyeep.app.client import ClientApp
from .messages import HeartBeat, Sample

from .heartrate import HeartRateMonitor
from .scene_heartbeat import SceneHeartbeat


class HeartrateCmd(ApplicationAsyncCmd):
    """Interactive heart rate reporting control."""

    def __init__(self, heartrate: "Heartrate") -> None:
        super().__init__()
        self.heartrate = heartrate

    async def do_quit(self, arg) -> None:
        raise AsyncCmdQuit()

    async def do_rate(self, arg) -> None:
        rate = float(arg)
        await self.heartrate.send(
            HeartBeat(sample=Sample(time=tm.time_ns(), rate=rate))
        )


class Heartrate(ClientApp):
    """Inspect the pyeep system."""

    def __init__(self, *, handle_sigterm_sigint: bool = True) -> None:
        super().__init__(
            name="heartrate", handle_sigterm_sigint=handle_sigterm_sigint
        )
        self.monitor: HeartRateMonitor | None = None
        if self.args.addr:
            self.monitor = HeartRateMonitor(
                device=self.args.addr, log=logging.getLogger(f"{self.name}.ble")
            )
        # TODO: move to a scene manager
        self.scene_heartbeat = SceneHeartbeat()
        self.add_component(self.scene_heartbeat)
        self.cmd = HeartrateCmd(self)

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    async def send_beats(self) -> None:
        assert self.monitor is not None
        async for sample in self.monitor.samples():
            print("Sample", sample)
            await self.send(HeartBeat(sample=sample))

    async def cmd_task(self) -> None:
        await self.cmd.async_cmdloop()
        await self.main_event_queue.put(AppShutdownEvent("User quit"))

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        if self.monitor is not None:
            tg.create_task(self.monitor.main())
            tg.create_task(self.send_beats())
        tg.create_task(self.scene_heartbeat.tick())
        tg.create_task(self.cmd_task())


if __name__ == "__main__":
    Heartrate.run()
