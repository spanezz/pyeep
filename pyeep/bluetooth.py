from __future__ import annotations

import asyncio
import re
from typing import NamedTuple, Sequence, Type

import bleak
import bleak.assigned_numbers

from .component.aio import AIOComponent
from .component.connected import ConnectedComponent, ConnectedState, ConnectedStateChanged
from .messages import Message, Shutdown, DeviceScanRequest

re_mangle = re.compile(r"[^\w]+")


class Device(NamedTuple):
    """
    Describe a known Bluetooth device
    """
    address: str
    component_cls: Type["BluetoothComponent"]
    # If not empty, the device detected must have service UUIDs that start wtih
    # all these strings
    service_uuid: tuple[str, ...] = ()


class BluetoothDisconnect(Message):
    """
    Message used only internally to trigger handling a device disconnect
    """
    pass


class BluetoothComponent(ConnectedComponent, AIOComponent):
    """
    Base class for components handling Bluetooth-connected devices
    """
    def __init__(self, device: bleak.backends.device.BLEDevice, **kwargs):
        kwargs.setdefault("name", re_mangle.sub("_", f"bt_{device.name}_{device.address}"))
        super().__init__(**kwargs)
        self.device = device
        self.client = bleak.BleakClient(
            self.device,
            disconnected_callback=self._on_disconnect,
        )
        self.connect_task: asyncio.Task | None = None
        self.task_group = asyncio.TaskGroup()
        self.connection_state: ConnectedState = ConnectedState.DISCONNECTED

    def get_connected_state(self):
        return self.connection_state

    def _update_connected_state(self, value: ConnectedState) -> None:
        if value == self.connection_state:
            return
        self.connection_state = value
        self.send(ConnectedStateChanged(value=value))

    async def on_connect(self):
        """
        Hook called when the device connects
        """
        self._update_connected_state(ConnectedState.CONNECTED)

    def _on_disconnect(self, client: bleak.BleakClient):
        self.receive(BluetoothDisconnect())

    async def _connect(self):
        """
        Connect to the device, waiting for it to come back in range if not
        reachable
        """
        while not self.client.is_connected:
            self.logger.info("(re)connecting device")
            self._update_connected_state(ConnectedState.CONNECTING)
            try:
                await self.client.connect(timeout=5)
            except bleak.exc.BleakError as e:
                self._update_connected_state(ConnectedState.DISCONNECTED)
                self.logger.warning("Cannot connect: %s", e)
            except TimeoutError as e:
                self._update_connected_state(ConnectedState.DISCONNECTED)
                self.logger.warning("Connect timeout: %s", e)
            else:
                break
            await asyncio.sleep(0.3)
        await self.on_connect()
        self.logger.info("connected")
        self.connect_task = None

    async def connect(self):
        if self.connect_task is None:
            self.connect_task = asyncio.create_task(self._connect())

    async def run_start(self):
        await self.connect()

    async def run_end(self):
        if self.connect_task is not None:
            self.connect_task.cancel()
            await self.connect_task
            self.connect_task = None
        # else:
        #     if self.client.is_connected:
        #         await self.client.disconnect()

    async def run_message(self, msg: Message) -> None:
        pass

    async def run(self):
        await self.run_start()
        try:
            while True:
                match (msg := await self.next_message()):
                    case Shutdown():
                        break
                    case BluetoothDisconnect():
                        self.logger.warning("device disconnected")
                        self._update_connected_state(ConnectedState.DISCONNECTED)
                        await self.connect()
                    case _:
                        await self.run_message(msg)
        finally:
            await self.run_end()


class Bluetooth(AIOComponent):
    """
    Scans for known BlueTooth devices, and instantiate their corresponding
    components when found
    """
    def __init__(self, devices: Sequence[Device], **kwargs):
        super().__init__(**kwargs)
        # Map device MAC addresses to Component classes to use for them
        self.devices = {d.address: d for d in devices}
        # Cache of already insantiated components
        self.components: dict[str, BluetoothComponent] = {}
        self.scanner = bleak.BleakScanner(
            self._scanner_event,
            # bleak.exc.BleakError: passive scanning on Linux requires BlueZ >= 5.55 with --experimental enabled
            #   and Linux kernel >= 5.10
            # scanning_mode="passive",
            # bluez={
            #     "or_patterns": [
            #         (0, bleak.assigned_numbers.AdvertisementDataType.FLAGS, b"\x06"),
            #         (0, bleak.assigned_numbers.AdvertisementDataType.FLAGS, b"\x1a"),
            #     ]
            # }
        )
        self.scan_task: asyncio.Task | None = None

    def _scanner_event(
            self,
            device: bleak.backends.device.BLEDevice,
            advertising_data: bleak.backends.scanner.AdvertisementData):
        # print("DEVICE", device.address, device.name)
        # print("EVENT", repr(device), repr(advertising_data))
        if (devinfo := self.devices.get(device.address)) is None:
            return

        # Already discovered
        if device.address in self.components:
            return

        # Filter by service UUID
        if devinfo.service_uuid:
            # print("LOOK for", devinfo.service_uuid, "IN", advertising_data.service_uuids)
            for val in devinfo.service_uuid:
                for uuid in advertising_data.service_uuids:
                    if uuid.startswith(val):
                        break
                else:
                    self.logger.warning(
                            "device %s %s service uuids %r do not match %r",
                            device.address, device.name,
                            advertising_data.service_uuids,
                            devinfo.service_uuid)
                    return

        self.logger.info("found device %s %s %s", device.address, device.name, advertising_data.rssi)

        self.components[device.address] = self.hub.app.add_component(
                devinfo.component_cls, device=device)

    async def _scan(self, duration: float = 2.0):
        self.logger.info("started scanning")
        await self.scanner.start()
        await asyncio.sleep(duration)
        await self.scanner.stop()
        self.scan_task = None
        self.logger.info("stopped scanning")

    async def scan(self, duration: float = 2.0):
        if self.scan_task is None:
            self.scan_task = asyncio.create_task(self._scan(duration=duration))

    async def run(self):
        await self.scan()

        try:
            while True:
                match (msg := await self.next_message()):
                    case Shutdown():
                        break
                    case DeviceScanRequest():
                        await self.scan(duration=msg.duration)
        finally:
            if self.scan_task is not None:
                self.scan_task.cancel()
                await self.scan_task
                self.scan_task = None
