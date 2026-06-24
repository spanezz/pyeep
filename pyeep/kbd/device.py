import abc
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, override, Any, Unpack

import evdev

from pyeep.nodes import Component, ComponentArgs
from pyeep.models.messages import Event

if TYPE_CHECKING:
    from .__main__ import Evdev


class RegistryEntry(NamedTuple):
    name: str
    device_name: str
    device_class: type["Device"]


class DeviceIgnored(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


class DeviceArgs(ComponentArgs):
    path: Path
    dev: evdev.InputDevice


class Device(Component, abc.ABC):
    # Map device names to device information
    REGISTRY: dict[str, RegistryEntry] = {}

    def __init__(
        self,
        *,
        path: Path,
        dev: evdev.InputDevice,
        **kwargs: Unpack[ComponentArgs],
    ) -> None:
        super().__init__(**kwargs)
        self.path = path
        self.dev = dev

    @override
    def __init_subclass__(
        cls,
        register: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Register known devices using this class.

        :param devices: mapping of device file names to component names
        """
        super().__init_subclass__(**kwargs)
        if register is None:
            return
        for device_name, component_name in register.items():
            cls.REGISTRY[device_name] = RegistryEntry(
                name=component_name, device_name=device_name, device_class=cls
            )

    @override
    async def main(self) -> None:
        try:
            async for ev in self.dev.async_read_loop():
                await self.on_evdev(ev)
        except OSError as exc:
            self.log.error("%s: %s", self.path, exc)

    @override
    async def send_event(self, msg: Event) -> None:
        self.log.info("Sending event %s", msg)
        await super().send_event(msg)

    @abc.abstractmethod
    async def on_evdev(self, evt: evdev.InputEvent) -> None:
        """Process an event from the device."""

    @classmethod
    def create(cls, *, path: Path, hub: "Evdev") -> "Device":
        if (devinfo := cls.REGISTRY.get(path.name)) is None:
            raise DeviceIgnored("device without a registry entry")

        try:
            dev = evdev.InputDevice(path)
        except PermissionError:
            raise DeviceIgnored(
                "insufficient permissions to access evdev device"
            )

        return devinfo.device_class(
            name=devinfo.name, path=path, dev=dev, hub=hub
        )
