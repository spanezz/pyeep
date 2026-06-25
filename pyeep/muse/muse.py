import asyncio
from typing import override, Unpack

from pyeep.nodes.bluetooth import BLEComponentArgs, BLEComponent

from . import aio_muse


class Muse(BLEComponent):
    """Interact with a Muse2 headband."""

    def __init__(self, **kwargs: Unpack[BLEComponentArgs]) -> None:
        super().__init__(**kwargs)
        self.muse: aio_muse.Muse | None = None
        self.cb_eeg: aio_muse.CallbackEEG | None = None
        self.cb_control: aio_muse.CallbackControl | None = None
        self.cb_telemetry: aio_muse.CallbackTelemetry | None = None
        self.cb_acc: aio_muse.CallbackACC | None = None
        self.cb_gyro: aio_muse.CallbackGyro | None = None
        self.cb_ppg: aio_muse.CallbackPPG | None = None

    @override
    async def connected(self) -> None:
        assert self.client is not None
        self.muse = aio_muse.Muse(self.client)
        await self.muse.resume()
        await self.refresh_subscriptions()
        try:
            await asyncio.Event().wait()
        finally:
            self.muse = None

    async def subscribe(
        self,
        eeg: aio_muse.CallbackEEG | None = None,
        control: aio_muse.CallbackControl | None = None,
        telemetry: aio_muse.CallbackTelemetry | None = None,
        acc: aio_muse.CallbackACC | None = None,
        gyro: aio_muse.CallbackGyro | None = None,
        ppg: aio_muse.CallbackPPG | None = None,
    ) -> None:
        self.cb_eeg = eeg
        self.cb_control = control
        self.cb_telemetry = telemetry
        self.cb_acc = acc
        self.cb_gyro = gyro
        self.cb_ppg = ppg
        if self.muse is not None:
            await self.refresh_subscriptions()

    async def refresh_subscriptions(self) -> None:
        assert self.muse is not None
        await self.muse.reset_subscriptions()
        if self.cb_eeg:
            await self.muse.subscribe_eeg(self.cb_eeg)
        if self.cb_control:
            await self.muse.subscribe_control(self.cb_control)
        if self.cb_telemetry:
            await self.muse.subscribe_telemetry(self.cb_telemetry)
        if self.cb_acc:
            await self.muse.subscribe_acc(self.cb_acc)
        if self.cb_gyro:
            await self.muse.subscribe_gyro(self.cb_gyro)
        if self.cb_ppg:
            await self.muse.subscribe_ppg(self.cb_ppg)
