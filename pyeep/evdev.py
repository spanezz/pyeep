from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Type

import aionotify
import evdev

import pyeep.aio
from .app import Shutdown

from .inputs import Input, InputSetActive, InputSetMode


class EvdevInput(Input, pyeep.aio.AIOComponent):
    """
    Input device processing events from an evdev device
    """
    def __init__(self, *, path: Path, device: evdev.InputDevice, **kwargs):
        kwargs.setdefault("name", "evdev_" + path.name)
        super().__init__(**kwargs)
        self.path = path
        self.device = device
        self.active = False

    @pyeep.aio.export
    def is_active(self) -> bool:
        return self.active

    @property
    def description(self) -> str:
        return self.device.name

    async def on_evdev(self, ev: evdev.InputEvent):
        print(repr(ev))

    async def read_events(self):
        try:
            async for ev in self.device.async_read_loop():
                await self.on_evdev(ev)
        except OSError as e:
            self.logger.error("%s: %s", self.path, e)
            self.receive(Shutdown())

    async def run(self):
        async with asyncio.TaskGroup() as tg:
            reader = tg.create_task(self.read_events())
            try:
                while True:
                    match (msg := await self.next_message()):
                        case Shutdown():
                            break
                        case InputSetActive():
                            if msg.input == self:
                                self.active = msg.value
                        case InputSetMode():
                            if msg.input == self:
                                self.mode = getattr(self, "mode_" + msg.mode)
            finally:
                reader.cancel()


class EvdevDeviceManager(pyeep.aio.AIOComponent):
    """
    Manage hotplugging of evdev devices.

    See https://www.enricozini.org/blog/2023/debian/handling-keyboard-like-devices/
    for tips about setting up exotic input devices
    """
    def __init__(self, device_map: dict[str, Type[Input]], **kwargs):
        """
        Device_map maps names of device files in /dev/input/by-id to Input
        subclasses to use to manage them
        """
        super().__init__(**kwargs)
        self.device_map = device_map
        self.components: dict[Path, Input] = {}
        self.root = Path('/dev/input/by-id')
        self.watcher = aionotify.Watcher()

    async def device_added(self, path: Path):
        if path in self.components:
            return

        if (component_cls := self.device_map.get(path.name)) is None:
            return

        try:
            device = evdev.InputDevice(path)
        except PermissionError:
            self.logger.debug("%s: insufficient permissions to access evdev device", path)
            return

        self.logger.info("%s: evdev device added", path)
        component = self.hub.app.add_component(component_cls, path=path, device=device)
        self.components[path] = component

    async def device_removed(self, path: Path):
        self.logger.info("%s: evdev device removed", path)
        if (component := self.components.get(path)) is not None:
            component.receive(Shutdown())

    async def watcher_task(self):
        self.watcher.watch(
            alias='devices',
            path=self.root.as_posix(),
            flags=aionotify.Flags.CREATE | aionotify.Flags.DELETE | aionotify.Flags.MOVED_TO)
        await self.watcher.setup(asyncio.get_event_loop())

        # Enumerate existing devices
        for path in self.root.iterdir():
            if path.name.startswith("."):
                continue
            await self.device_added(path)

        try:
            while True:
                event = await self.watcher.get_event()
                if event.name.startswith("."):
                    continue

                if event.flags & (aionotify.Flags.CREATE | aionotify.Flags.MOVED_TO):
                    await self.device_added(self.root / event.name)
                elif event.flags & aionotify.Flags.DELETE:
                    await self.device_removed(self.root / event.name)
        except asyncio.CancelledError:
            pass
        finally:
            self.watcher.close()

    async def run(self):
        async with asyncio.TaskGroup() as tg:
            device_watcher = tg.create_task(self.watcher_task())

            try:
                while True:
                    match await self.next_message():
                        case Shutdown():
                            break
            finally:
                device_watcher.cancel()
