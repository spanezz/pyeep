import asyncio
import enum
import logging
import math
import struct
from typing import override, Unpack

import bleak
import bleak.backends

from pyeep.nodes.bluetooth import BLEComponent, BLEComponentArgs
from pyeep.models.messages.buttons import ButtonEvent
from pyeep.models.messages.position import OrientationEvent, AccelerationEvent

# See https://github.com/Ludsota/DG-LAB-Bluetooth-Protocole/blob/main/Pawprints/PROTOCOL.md
COMMAND_UUID = "0000150a-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000150b-0000-1000-8000-00805f9b34fb"


class Color(enum.IntEnum):
    """Pawprint identification color."""

    YELLOW = 1
    RED = 2
    VIOLET = 3
    BLUE = 4
    CYAN = 5
    GREEN = 6


class Pawprint(BLEComponent):
    """Interact with a DG-Lab Pawprint device."""

    def __init__(self, **kwargs: Unpack[BLEComponentArgs]) -> None:
        super().__init__(**kwargs)
        self.color = Color.YELLOW
        self.stream: bool = False
        self.btn0_pressed: bool = False
        self.btn1_pressed: bool = False
        self.btn2_pressed: bool = False

    @override
    async def connected(self) -> None:
        assert self.client is not None
        await self.client.start_notify(NOTIFY_UUID, self.on_data)
        await self.set_stream(True)
        await asyncio.Event().wait()

    async def set_color(self, color: Color) -> None:
        self.color = color
        await self.sync()

    async def set_stream(self, value: bool) -> None:
        self.log.info("%s stream", "Starting" if value else "Stopping")
        self.stream = value
        await self.sync()

    async def sync(self) -> None:
        """Sync state to the pawprint."""
        assert self.client is not None
        command = struct.pack(
            "BBB", 0x53, self.color, 0 if not self.stream else 0xFF
        )
        await self.client.write_gatt_char(COMMAND_UUID, command)

    async def on_data(
        self,
        characteristic: bleak.backends.characteristic.BleakGATTCharacteristic,
        data: bytearray,
    ) -> None:
        """
        Decode pawprint information
        """
        if len(data) < 13:
            logging.warning(
                "%d byte buffer received (too short): %s",
                len(data),
                data.hex(" "),
            )
            return
        if len(data) > 13:
            logging.warning(
                "%d byte buffer received (too long): %s",
                len(data),
                data.hex(" "),
            )
        btn0, btn1, btn2, voltage, x, y, z = struct.unpack(
            ">BBBLhhh", data[:13]
        )

        # 0: pressed, 1: released
        if (btn0 == 0) != self.btn0_pressed:
            self.btn0_pressed = btn0 == 0
            await self.hub.send_event(
                ButtonEvent(
                    key="BTN0", action="down" if self.btn0_pressed else "up"
                )
            )
        if (btn1 == 0) != self.btn1_pressed:
            self.btn1_pressed = btn1 == 0
            await self.hub.send_event(
                ButtonEvent(
                    key="BTN1", action="down" if self.btn1_pressed else "up"
                )
            )
        if (btn2 == 0) != self.btn2_pressed:
            self.btn2_pressed = btn2 == 0
            await self.hub.send_event(
                ButtonEvent(
                    key="BTN2", action="down" if self.btn2_pressed else "up"
                )
            )

        fx = x / 128 * 9.8
        fy = y / 128 * 9.8
        fz = z / 128 * 9.8

        roll = math.atan2(fy, fz) / math.pi * 180
        pitch = math.atan2(-fx, math.sqrt(fy * fy + fz * fz)) / math.pi * 180
        await self.hub.send_event(OrientationEvent(pitch=pitch, roll=roll))

        mag = math.sqrt(fx**2 + fy**2 + fz**2)
        acc = abs(mag - 9.8)

        # logging.info(
        #     "Pawprint btn0:%s btn1:%s btn2:%s V:%d x:%d y:%d z:%d, pitch:%f, roll:%f, mag:%f, a:%f",
        #     btn0,
        #     btn1,
        #     btn2,
        #     voltage,
        #     x,
        #     y,
        #     z,
        #     pitch,
        #     roll,
        #     mag,
        #     acc,
        # )
        await self.hub.send_event(AccelerationEvent(value=acc))
