import abc
import logging
import inspect
import json
import math
from pathlib import Path
from typing import Any, override

import numpy
import scipy.signal

from pyeep.utils import dsp
from pyeep.app.base import BaseApp, AppSendMessageEvent

from .messages import HeadMoved, HeadYesNo, HeadGyro
from .muse import Muse
from . import aio_muse

#: Mode registry
modes: dict[str, "type[Mode]"] = {}


class Mode(abc.ABC):
    """Base class for Muse2 data processing modes."""

    name: str

    @override
    def __init_subclass__(
        cls,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Register this class as a mode."""
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls.name = name or cls.__name__.lower()
        modes[cls.name] = cls

    def __init__(self, *, muse: "Muse", app: BaseApp) -> None:
        self.muse = muse
        self.app = app

    @abc.abstractmethod
    async def start(self) -> None:
        """Start processing Muse data."""


class ModeHeadPosition(Mode, name="headpos"):
    """Head position."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.filter_pitch = dsp.Butterworth(rate=52, cutoff=15)
        self.filter_roll = dsp.Butterworth(rate=52, cutoff=15)

    @override
    async def start(self) -> None:
        await self.muse.subscribe(acc=self.on_acc)

    def on_acc(
        self, data: aio_muse.SamplesACC, timestamps: aio_muse.Timestamps
    ) -> None:
        frames = len(timestamps)
        for i in range(frames):
            x = data[0, i]
            y = data[1, i]
            z = data[2, i]

            roll = math.atan2(y, z) / math.pi * 180
            pitch = math.atan2(-x, math.sqrt(y * y + z * z)) / math.pi * 180

            roll = self.filter_roll(roll)
            pitch = self.filter_pitch(pitch)

        self.app.main_event_queue.put_nowait(
            AppSendMessageEvent(
                message=HeadMoved(frames=frames, pitch=pitch, roll=roll)
            )
        )


class GyroAxisBase(abc.ABC):
    """Handle data from a Gyro axis."""

    def __init__(self, name: str):
        """
        Initialize the GyroAxis.

        :param name: axis name
        """
        self.name = name
        self.calibration_path = Path(f".cal_gyro_{name}")
        # Samples used to compute the axis bias
        self.bias_samples: list[float] = []
        # Acceleration bias for this axis
        self.bias: float | None = None
        if self.calibration_path.exists():
            data = json.loads(self.calibration_path.read_text())
            self.bias = data["bias"]

    def add(self, timestamp: float, sample: float) -> None:
        """Add a sample for the axis."""
        if self.bias is None:
            if len(self.bias_samples) < 256:
                self.bias_samples.append(sample)
            else:
                self.bias = numpy.mean(self.bias_samples)
                self.calibration_path.write_text(
                    json.dumps({"bias": self.bias})
                )
        else:
            self.process_sample(timestamp, sample - self.bias)

    def add_samples(self, timestamps: list[float], samples: numpy.ndarray):
        for ts, sample in zip(timestamps, samples):
            self.add(ts, sample)

    @abc.abstractmethod
    def process_sample(self, timestamp: float, sample: float) -> None:
        """Process a gyro sample for this axis."""


class GyroAxisSwing(GyroAxisBase):
    """Tracks back and forth swings on an axis."""

    def __init__(self, name: str, *, gesture: str, max_dps: float) -> None:
        """
        Initialize the GyroAxisSwing.

        :param name: axis name
        :param gesture: gesture name
        :param max_dps: maximum degrees per second to report
        """
        super().__init__(name)
        self.gesture = gesture
        self.max_dps = max_dps
        #: Sign of the acceleration of the last gesture seen
        self.sign: float | None = None
        #: Time of the start of the last gesture
        self.gesture_start: float | None = None
        #: Time of the end of the last gesture
        self.gesture_end: float | None = None
        #: Total angle in the last gesture
        self.total_angle: float = 0

    @override
    def process_sample(self, timestamp: float, sample: float) -> None:
        sign = math.copysign(1, sample)
        if self.sign is None or self.sign != sign:
            # Start a new gesture
            self.sign = sign
            self.gesture_start = timestamp
            self.total_angle = 0
        self.total_angle += sample
        self.gesture_end = timestamp

    def value(self) -> tuple[float, float]:
        """
        Return the gesture duration (seconds) and intensity (from 0 to 1) since
        the last direction change
        """
        if self.gesture_end is None:
            return 0, 0
        else:
            assert self.gesture_start is not None
            elapsed = self.gesture_end - self.gesture_start
            if elapsed == 0:
                return 0, 0
            dps = abs(self.total_angle / 52 / elapsed)
            return elapsed, numpy.clip(dps / self.max_dps, 0, 1)


class GyroAxisLast(GyroAxisBase):
    """Track the last acceleration value for a gyro axis."""

    def __init__(self, name: str):
        super().__init__(name)
        #: Last acceleration value
        self.last: float = 0
        #: Difference between the last and the previous values
        self.alast: float = 0

    @override
    def process_sample(self, timestamp: float, sample: float):
        self.alast = sample - self.last
        self.last = sample

    def value(self) -> tuple[float, float]:
        """Return the angular velocity along this axis."""
        return self.last, self.alast


class ModeHeadYesNo(Mode, name="yesno"):
    """Head yes/no."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.x_axis = GyroAxisSwing("x", gesture="meh", max_dps=200)
        self.y_axis = GyroAxisSwing("y", gesture="yes", max_dps=150)
        self.z_axis = GyroAxisSwing("z", gesture="no", max_dps=200)

    @override
    async def start(self) -> None:
        await self.muse.subscribe(gyro=self.on_gyro)

    def on_gyro(
        self, data: aio_muse.SamplesGyro, timestamps: aio_muse.Timestamps
    ):
        self.x_axis.add_samples(timestamps, data[0, :])
        self.y_axis.add_samples(timestamps, data[1, :])
        self.z_axis.add_samples(timestamps, data[2, :])

        selected: tuple[str, float, float] | None = None
        for axis in self.x_axis, self.y_axis, self.z_axis:
            duration, intensity = axis.value()
            if duration < 0.05:
                continue
            if intensity < 0.1:
                continue
            if selected is None or selected[2] < intensity:
                selected = (axis.gesture, duration, intensity)

        if selected is None:
            return

        self.app.main_event_queue.put_nowait(
            AppSendMessageEvent(
                HeadYesNo(
                    gesture=selected[0],
                    duration=selected[1],
                    intensity=selected[2],
                )
            )
        )


class ModeHeadGyro(Mode, name="headgyro"):
    """Head gyro values."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.x_axis = GyroAxisLast("x")
        self.y_axis = GyroAxisLast("y")
        self.z_axis = GyroAxisLast("z")

    @override
    async def start(self) -> None:
        try:
            await self.muse.subscribe(gyro=self.on_gyro)
        except Exception as e:
            logging.error("start exception %s", e, exc_info=e)

    def on_gyro(
        self, data: aio_muse.SamplesGyro, timestamps: aio_muse.Timestamps
    ):
        self.x_axis.add_samples(timestamps, data[0, :])
        self.y_axis.add_samples(timestamps, data[1, :])
        self.z_axis.add_samples(timestamps, data[2, :])

        self.app.main_event_queue.put_nowait(
            AppSendMessageEvent(
                HeadGyro(
                    x=self.x_axis.value()[0],
                    y=self.y_axis.value()[0],
                    z=self.z_axis.value()[0],
                )
            )
        )


# class ModeBrainWaves(ModeBase):
#     """
#     Brain waves
#     """
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.win_size = 256 * 2
#         self.hop = 16
#         self.hamming = scipy.signal.windows.hamming(self.win_size, sym=False)
#         self.freqs = numpy.fft.fftfreq(self.win_size, 1 / 256)
#         self.timestamps: numpy.ndarray | None = None
#         self.samples: dict[str, numpy.ndarray] = {}
#         self.channels = ["TP9", "AF7", "AF8", "TP10"]
#         self.dend: int | None = None
#         self.tend: int | None = None
#         self.aend: int | None = None
#         self.bend: int | None = None
#         self.gend: int | None = None
#         for idx, val in enumerate(self.freqs):
#             if self.dend is None and val >= 4:
#                 self.dend = idx
#             elif self.tend is None and val >= 7.5:
#                 self.tend = idx
#             elif self.aend is None and val >= 12:
#                 self.aend = idx
#             elif self.bend is None and val >= 40:
#                 self.bend = idx
#             elif self.gend is None and val >= 70:
#                 self.gend = idx
#
#     def on_eeg(self, data: numpy.ndarray, timestamps: numpy.ndarray):
#         if self.timestamps is None:
#             self.timestamps = timestamps
#             for idx, name in enumerate(self.channels, start=1):
#                 self.samples[name] = data[idx, :]
#             return
#
#         self.timestamps = numpy.concatenate((self.timestamps, timestamps))
#         for idx, name in enumerate(self.channels, start=0):
#             old = self.samples.get(name)
#             self.samples[name] = numpy.concatenate((old, data[idx, :]))
#
#         if len(self.timestamps) >= self.win_size:
#             window_end_time = self.timestamps[self.win_size - 1]
#
#             all_delta: float = 0.0
#             all_theta: float = 0.0
#             all_alpha: float = 0.0
#             all_beta: float = 0.0
#             all_gamma: float = 0.0
#
#             for idx, name in enumerate(self.channels, start=1):
#                 arr = self.samples[name]
#
#                 signal = arr[: self.win_size] * self.hamming
#                 powers = abs(scipy.fft.rfft(signal))
#
#                 ch_delta = numpy.mean(20 * numpy.log10(powers[0 : self.dend]))
#                 ch_theta = numpy.mean(
#                     20 * numpy.log10(powers[self.dend : self.tend])
#                 )
#                 ch_alpha = numpy.mean(
#                     20 * numpy.log10(powers[self.tend : self.aend])
#                 )
#                 ch_beta = numpy.mean(
#                     20 * numpy.log10(powers[self.aend : self.bend])
#                 )
#                 ch_gamma = numpy.mean(
#                     20 * numpy.log10(powers[self.bend : self.gend])
#                 )
#
#                 all_delta += ch_delta
#                 all_theta += ch_theta
#                 all_alpha += ch_alpha
#                 all_beta += ch_beta
#                 all_gamma += ch_gamma
#
#                 self.samples[name] = arr[self.hop :]
#
#             self.timestamps = self.timestamps[self.hop :]
#
#             delta = all_delta / 4
#             theta = all_theta / 4
#             alpha = all_alpha / 4
#             beta = all_beta / 4
#             gamma = all_gamma / 4
#             # print(f"{window_end_time} {delta=:.1f} {theta=:.1f} {alpha=:.1f} {beta=:.1f} {gamma=:.1f}")
#             self.muse2.send(
#                 BrainWaves(
#                     timestamp=window_end_time,
#                     alpha=alpha,
#                     beta=beta,
#                     gamma=gamma,
#                     delta=delta,
#                     theta=theta,
#                 )
#             )
#
#
#
#
# # class GyroAxisFFT(GyroAxisBase):
# #     def __init__(self, name: str):
# #         super().__init__(name)
# #         # sample rate = 52
# #         self.window_len = 64
# #         self.window: deque[float] = deque(maxlen=self.window_len)
# #         self.hamming = scipy.signal.windows.hamming(self.window_len, sym=False)
# #
# #     def process_sample(self, timestamp: float, sample: float):
# #         self.window.append(sample - self.bias)
# #
# #     def value(self) -> tuple[float, float]:
# #         """
# #         Return frequency and power for the frequency band with the highest
# #         power, computed on the samples in the window
# #         """
# #         if len(self.window) == self.window_len:
# #             signal = self.hamming * self.window
# #             powers = abs(scipy.fft.rfft(signal))
# #             freqs = numpy.fft.fftfreq(len(self.window), 1/52)
# #             idx = numpy.argmax(powers[:32])
# #             return freqs[idx], powers[idx]
# #         else:
# #             return 0, 0
#
#
#
#
# class Muse2(SimpleActiveComponent, Input, bluetooth.BluetoothComponent):
#     """
#     Monitor a Bluetooth LE heart rate monitor
#     """
#
#     MODES = {
#         "default": ModeDefault,
#         "headpos": ModeHeadPosition,
#         "headgest": ModeHeadYesNo,
#         "headturn": ModeHeadGyro,
#         "brainwaves": ModeBrainWaves,
#     }
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.muse = Muse(self.client)
#
#     def get_controller(self) -> Type["InputController"]:
#         return Muse2InputController
#
#     async def on_connect(self):
#         await super().on_connect()
#         await self.muse.subscribe_gyro(self.on_gyro)
#         await self.muse.subscribe_acc(self.on_acc)
#         await self.muse.subscribe_eeg(self.on_eeg)
#         await self.muse.start()
#
#     def on_gyro(self, data: numpy.ndarray, timestamps: list[float]):
#         if not self.active:
#             return
#         self.mode.on_gyro(data, timestamps)
#
#     def on_acc(self, data: numpy.ndarray, timestamps: list[float]):
#         if not self.active:
#             return
#         self.mode.on_acc(data, timestamps)
#
#     def on_eeg(self, data: numpy.ndarray, timestamps: list[float]):
#         if not self.active:
#             return
#         self.mode.on_eeg(data, timestamps)
#
#     def list_modes(self) -> Iterator[ModeInfo, None]:
#         """
#         List available modes
#         """
#         for name, value in self.MODES.items():
#             yield ModeInfo(name, inspect.getdoc(value))
#
#     @export
#     def set_mode(self, name: str) -> None:
#         """
#         Set the active mode
#         """
#         self.mode = self.MODES[name](muse2=self)
#
#     # TODO: send keep_alive messages every once in a while
#
#
# class Muse2InputController(InputController):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.monitor = Gtk.EntryBuffer()
#         self.last_msg_hg: HeadGyro | None = None
#         self.last_msg_hga: HeadGyro | None = None
#         self.last_msg_mv: HeadMoved | None = None
#
#     def on_reset(self, button):
#         self.last_msg_hg = None
#         self.last_msg_hga = None
#         self.last_msg_mv = None
#         self.monitor.set_text("", 0)
#
#     def build(self) -> ControllerWidget:
#         cw = super().build()
#         monitor = Gtk.Text(buffer=self.monitor)
#         cw.box.append(monitor)
#
#         reset = Gtk.Button(label="reset")
#         reset.connect("clicked", self.on_reset)
#         cw.box.append(reset)
#         return cw
#
#     def receive(self, msg: Message):
#         match msg:
#             # case HeadGyro():
#             #     maxxed = False
#             #     if self.last_msg_hg is None or self.last_msg_hg._distance2() < msg._distance2():
#             #         self.last_msg_hg = msg
#             #         maxxed = True
#             #     if self.last_msg_hga is None or self.last_msg_hga._adistance2() < msg._adistance2():
#             #         self.last_msg_hga = msg
#             #         maxxed = True
#             #     if maxxed:
#             #         text = ""
#             #         if (m := self.last_msg_hg):
#             #             text += f"x={m.x:.2f} y={m.y:.2f} z={m.z:.2f}"
#             #         if (m := self.last_msg_hga):
#             #             if text:
#             #                 text += " "
#             #             text += f"ax={m.ax:.2f} ay={m.ay:.2f} az={m.az:.2f}"
#             #         self.monitor.set_text(text, len(text))
#
#             case HeadMoved():
#                 if (
#                     self.last_msg_mv is None
#                     or self.last_msg_mv._distance2() < msg._distance2()
#                 ):
#                     self.last_msg_mv = msg
#                     text = f"pitch={msg.pitch:.1f} roll={msg.roll:.1f}"
#                     self.monitor.set_text(text, len(text))
#
#
# # Old lsl-based components
# # from pyeep.lsl import LSLComponent, LSLSamples
# #
# # class HeadPosition(Input, LSLComponent):
# #     def __init__(self, **kwargs):
# #         kwargs.setdefault("stream_type", "ACC")
# #         kwargs.setdefault("max_samples", 8)
# #         super().__init__(**kwargs)
# #         self.active = False
# #
# #     @pyeep.aio.export
# #     @property
# #     def is_active(self) -> bool:
# #         return self.active
# #
# #     @property
# #     def description(self) -> str:
# #         return "Head position"
# #
# #     async def run(self):
# #         while True:
# #             msg = await self.next_message()
# #             match msg:
# #                 case Shutdown():
# #                     break
# #                 case InputSetActive():
# #                     if msg.input == self:
# #                         self.active = msg.value
# #                 case LSLSamples():
# #                     if self.active:
# #                         await self.process_samples(msg.samples, msg.timestamps)
# #
# #     async def process_samples(self, samples: list, timestamps: list):
# #         data = numpy.array(samples, dtype=float)
# #
# #         # TODO: replace with a low-pass filter?
# #         x = numpy.mean(data[:, 0])
# #         y = numpy.mean(data[:, 1])
# #         z = numpy.mean(data[:, 2])
# #
# #         roll = math.atan2(y, z) / math.pi * 180
# #         pitch = math.atan2(-x, math.sqrt(y*y + z*z)) / math.pi * 180
# #
# #         self.send(HeadMoved(pitch=pitch, roll=roll))
# #
# #
# # class HeadMovement(Input, LSLComponent):
# #     def __init__(self, **kwargs):
# #         kwargs.setdefault("stream_type", "GYRO")
# #         kwargs.setdefault("max_samples", 8)
# #         super().__init__(**kwargs)
# #         self.x_axis = GyroAxis("x")
# #         self.y_axis = GyroAxis("y")
# #         self.z_axis = GyroAxis("z")
# #         self.active = False
# #
# #     @pyeep.aio.export
# #     @property
# #     def is_active(self) -> bool:
# #         return self.active
# #
# #     @property
# #     def description(self) -> str:
# #         return "Head movement"
# #
# #     async def run(self):
# #         while True:
# #             msg = await self.next_message()
# #             match msg:
# #                 case Shutdown():
# #                     break
# #                 case InputSetActive():
# #                     if msg.input == self:
# #                         self.active = msg.value
# #                 case LSLSamples():
# #                     if self.active:
# #                         await self.process_samples(msg.samples, msg.timestamps)
# #
# #     async def process_samples(self, samples: list, timestamps: list):
# #         for x, y, z in samples:
# #             self.x_axis.add(x)
# #             self.y_axis.add(y)
# #             self.z_axis.add(z)
# #
# #         selected = None
# #         for axis in (self.x_axis, self.y_axis, self.z_axis):
# #             freq, power = axis.fft_value()
# #             if selected is None or selected[2] < power:
# #                 selected = (axis.name, freq, power)
# #
# #         if selected[2] > 500:
# #             self.send(
# #                 HeadShaken(axis=selected[0], freq=selected[1], power=10*math.log10(selected[2] ** 2))
# #             )
