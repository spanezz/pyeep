import asyncio
from pathlib import Path
from typing import override, Unpack, AsyncGenerator

import aionotify

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import BaseAppArgs

from .device import Device, DeviceIgnored

# Import keyboards so they get registered in the device registry
from . import keyboards  # noqa: F401


class KeyboardDefinition:
    def __init__(self, name: str) -> None:
        self.name = name


class DeviceWatcherEvent:
    def __init__(self, path: Path):
        self.path = path


class DeviceAdded(DeviceWatcherEvent):
    pass


class DeviceRemoved(DeviceWatcherEvent):
    pass


async def monitor_device_presence(
    root: Path = Path("/dev/input/by-id"),
) -> AsyncGenerator[DeviceWatcherEvent]:
    """Monitor the presence of evdev devices, generating DeviceWatcherEvent."""
    watcher = aionotify.Watcher()
    watcher.watch(
        alias="devices",
        path=root.as_posix(),
        flags=aionotify.Flags.CREATE
        | aionotify.Flags.DELETE
        | aionotify.Flags.MOVED_TO,
    )
    await watcher.setup(asyncio.get_running_loop())

    # Enumerate existing devices
    for path in root.iterdir():
        if path.name.startswith("."):
            continue
        yield DeviceAdded(path)

    try:
        while True:
            event = await watcher.get_event()
            if event.name.startswith("."):
                continue

            if event.flags & (
                aionotify.Flags.CREATE | aionotify.Flags.MOVED_TO
            ):
                yield DeviceAdded(root / event.name)
            elif event.flags & aionotify.Flags.DELETE:
                yield DeviceRemoved(root / event.name)
    except asyncio.CancelledError:
        pass
    finally:
        watcher.close()


class Evdev(ApplicationAsyncCmdClientApp):
    """Evdev-based event generator."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.devices: dict[Path, Device] = {}

    async def add_device(self, path: Path) -> None:
        try:
            device = Device.create(path=path, hub=self)
        except DeviceIgnored as exc:
            self.log.info("%s: ignoring device: %s", path, exc.reason)
            return

        self.devices[path] = device
        await self.add_component(device)
        self.log.info("%s: device %s added", path, device.name)

    async def remove_device(self, path: Path) -> None:
        if (device := self.devices.pop(path, None)) is None:
            return
        await self.remove_component(device)
        self.log.info("%s: device %s removed", path, device.name)

    async def device_task(self) -> None:
        async for evt in monitor_device_presence():
            match evt:
                case DeviceAdded():
                    await self.add_device(evt.path)
                case DeviceRemoved():
                    await self.remove_device(evt.path)

    @override
    async def init(self) -> None:
        await super().init()
        await self.start_task(self.device_task())

    async def cmd_ls(self) -> None:
        for dev in self.devices.values():
            self.interface.term.add_line(
                [("bold", dev.name), ("", ": "), ("", str(dev.path))]
            )


if __name__ == "__main__":
    Evdev.run()
