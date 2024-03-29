from __future__ import annotations

import time
from typing import NamedTuple, Type

import bleak

from .. import bluetooth
from ..component.controller import ControllerWidget
from ..component.active import SimpleActiveComponent
from ..component.connected import ConnectedController
from ..gtk import Gtk
from ..messages.message import Message
from .base import Input, InputController

HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


class Sample(NamedTuple):
    """
    Data from a sample reported by the heartbeat monitor
    """
    # UNIX timestamp in nanoseconds
    time: int
    rate: float
    rr: tuple[float, ...] = ()


class HeartBeat(Message):
    """
    Heartbeat information notification event
    """
    def __init__(self, *, sample: Sample, **kwargs):
        super().__init__(**kwargs)
        self.sample = sample

    def __str__(self):
        return super().__str__() + f"(sample={self.sample})"


class HeartRateMonitor(SimpleActiveComponent, Input, bluetooth.BluetoothComponent):
    """
    Monitor a Bluetooth LE heart rate monitor
    """
    # This has been tested with a Moofit HW401

    def get_controller(self) -> Type["InputController"]:
        return HeartRateInputController

    async def on_connect(self):
        await super().on_connect()
        # FIXME: is this needed in case of reconnects?
        await self.client.start_notify(HEART_RATE_UUID, self.on_heart_rate)

    def on_heart_rate(self, characteristic: bleak.backend.characteristic.BleakGATTCharacteristic, data: bytearray):
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

        sample = Sample(time=time.time_ns(), rate=float(hr), rr=tuple(rr))
        self.on_sample(sample)

    def on_sample(self, sample: Sample):
        """
        Handle a new heart rate sample
        """
        if self.active:
            self.mode(sample=sample)

    def mode_default(self, sample: Sample):
        self.send(HeartBeat(sample=sample))


class HeartRateInputController(ConnectedController[HeartRateMonitor], InputController[HeartRateMonitor]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_rate = Gtk.Label(label="-- BPM")

    def build(self) -> ControllerWidget:
        cw = super().build()
        cw.box.append(self.current_rate)
        return cw

    def receive(self, msg: Message):
        if msg.src != self.component:
            return

        match msg:
            case HeartBeat():
                self.current_rate.set_label(f"{msg.sample.rate} BPM")
            case _:
                super().receive(msg)
