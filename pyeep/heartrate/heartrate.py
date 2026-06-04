import asyncio
import logging
import time as tm
from typing import override, AsyncGenerator

import bleak
import bleak.backends

from pyeep.bluetooth import BLEConnection

from .messages import Sample

HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
# HEART_RATE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"


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
