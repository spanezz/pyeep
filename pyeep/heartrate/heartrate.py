import abc
import asyncio
import logging
import time as tm
from typing import override, AsyncGenerator

import bleak
import bleak.backends

# from pyeep.components import Component
# from pyeep.models.messages.message import Message
from .messages import Sample, HeartBeat

HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
# HEART_RATE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"


class BLEConnection(abc.ABC):
    """Connect to a Bluetooth LE gadget."""

    def __init__(
        self,
        *,
        device: bleak.backends.device.BLEDevice | str,
        log: logging.Logger,
    ) -> None:
        self.device = device
        self.log = log
        self.client: bleak.BleakClient | None = None
        self.event_queue: asyncio.Queue[str] = asyncio.Queue()
        self.connected_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Manage (re)connection to the device."""
        while True:
            disconnect = asyncio.Event()

            def _on_disconnect(client: bleak.BleakClient) -> None:
                disconnect.set()

            self.log.info("(Re)connecting device")
            try:
                async with bleak.BleakClient(
                    self.device, disconnected_callback=_on_disconnect, timeout=5
                ) as client:
                    self.log.info("Connected")
                    self.client = client
                    await self.event_queue.put("connected")
                    await disconnect.wait()
            except TimeoutError as exc:
                self.log.warning("Cannot connect: %s", exc)
            finally:
                self.log.warning("Disconnected")
                self.client = None
                await self.event_queue.put("disconnected")

    async def main(self) -> None:
        """Main handling of the device."""
        connected_task: asyncio.Task | None = None
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.connect())
            while True:
                match (evt := await self.event_queue.get()):
                    case "connected":
                        connected_task = tg.create_task(self.connected())
                    case "disconnected":
                        if connected_task is not None:
                            connected_task.cancel()
                        connected_task = None
                    case _:
                        self.log.error("unknown event: %r", evt)
                self.event_queue.task_done()

    @abc.abstractmethod
    async def connected(self) -> None:
        """Called on connect, cancelled on disconnect."""

    # async def connect(self):
    #     """
    #     Connect to the device, waiting for it to come back in range if not
    #     reachable
    #     """
    #     while not self.client.is_connected:
    #         self.log.info("(re)connecting device")
    #         # self._update_connected_state(ConnectedState.CONNECTING)
    #         try:
    #             await self.client.connect(timeout=5)
    #         except bleak.exc.BleakError as e:
    #             # self._update_connected_state(ConnectedState.DISCONNECTED)
    #             self.log.warning("Cannot connect: %s", e)
    #         except TimeoutError as e:
    #             # self._update_connected_state(ConnectedState.DISCONNECTED)
    #             self.log.warning("Connect timeout: %s", e)
    #         else:
    #             break
    #         await asyncio.sleep(0.3)
    #     await self.on_connect()
    #     self.log.info("connected")
    #     # self.connect_task = None


class HeartRateMonitor(BLEConnection):
    """Monitor a Bluetooth LE heart rate monitor."""

    def __init__(
        self,
        *,
        device: bleak.backends.device.BLEDevice | str,
        log: logging.Logger,
    ) -> None:
        super().__init__(device=device, log=log)
        self.sample_queue: asyncio.Queue[Sample] = asyncio.Queue()

    @override
    async def connected(self) -> None:
        assert self.client is not None
        await self.client.start_notify(HEART_RATE_UUID, self.on_heart_rate)
        # TODO: also start_notify BATTERY_SERVICE_UUID
        await asyncio.Event().wait()

    async def samples(self) -> AsyncGenerator[Sample]:
        while True:
            sample = await self.sample_queue.get()
            yield sample
            self.sample_queue.task_done()

    async def on_heart_rate(
        self,
        characteristic: bleak.backends.characteristic.BleakGATTCharacteristic,
        data: bytearray,
    ):
        """
        Decode heart rate information
        """
        # From https://github.com/fg1/BLEHeartRateLogger
        # See https://www.mariam.qa/post/hr-ble/
        # RR intervals are the intervals in milliseconds between heart beats:
        # see https://help.elitehrv.com/article/67-what-are-r-r-intervals
        # log.info("%s: %r", characteristic.description, data)

        byte0 = data[0]
        hrv_uint8 = (byte0 & 1) == 0

        # sensor_contact = (byte0 >> 1) & 3
        # if sensor_contact == 2:
        #     res["sensor_contact"] = "No contact detected"
        # elif sensor_contact == 3:
        #     res["sensor_contact"] = "Contact detected"
        # else:
        #     res["sensor_contact"] = "Sensor contact not supported"

        # Energy expended present
        have_ee = ((byte0 >> 3) & 1) == 1

        # RR intervals present
        have_rr = ((byte0 >> 4) & 1) == 1

        if hrv_uint8:
            hr = data[1]
            i = 2
        else:
            hr = (data[2] << 8) | data[1]
            i = 3

        if have_ee:
            # ee = (data[i + 1] << 8) | data[i]
            i += 2

        rr: list[float] = []
        if have_rr:
            while i < len(data):
                # Note: Need to divide the value by 1024 to get in seconds
                rr_val = (data[i + 1] << 8) | data[i]
                rr.append(rr_val / 1024)
                i += 2

        sample = Sample(time=tm.time_ns(), rate=float(hr), rr=tuple(rr))
        await self.sample_queue.put(sample)


#    def on_sample(self, sample: Sample):
#        """
#        Handle a new heart rate sample
#        """
#        if self.active:
#            self.mode(sample=sample)
#
#    def mode_default(self, sample: Sample):
#        self.send(HeartBeat(sample=sample))
