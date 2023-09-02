from __future__ import annotations

import math
from typing import Type

import jack
import numba
from numba.experimental import jitclass

import pyeep.outputs
from pyeep.component.aio import AIOComponent
from pyeep.component.base import export
from pyeep.component.jack import JackComponent

from .power import PowerOutput, PowerOutputController


# class PlayAudio(Message):
#     def __init__(self, last_frame_time: int, frames: int, audio: numpy.ndarray, **kwargs):
#         super().__init__(**kwargs)
#         self.last_frame_time = last_frame_time
#         self.frames = frames
#         self.audio = audio
#
#     def __str__(self) -> str:
#         return super().__str__() + (
#                 f"(last_frame_time={self.last_frame_time},"
#                 f" frames={self.frames},"
#                 f" audio={len(self.audio)})")


@jitclass([
    ("rate", numba.int32),
    ("phase", numba.float64),
])
class SimpleSynth:
    """
    Phase accumulation synthesis
    """
    # See https://www.gkbrk.com/wiki/PhaseAccumulator/

    def __init__(self, rate: int):
        self.rate: int = rate
        self.phase: float = 0.0

    def synth(self, buf: memoryview, frames: int, freq: float, power: float) -> None:
        for i in range(frames):
            if power == 0.0:
                buf[i] = 0
            else:
                self.phase += 2.0 * math.pi * freq / self.rate
                buf[i] = math.sin(self.phase) * power


class Pulses(PowerOutput, JackComponent, AIOComponent):
    def __init__(self, **kwargs):
        super().__init__(rate=0, **kwargs)
        self.power: float = 0.0
        self.synth: SimpleSynth

    def set_jack_client(self, jack_client: jack.Client):
        super().set_jack_client(jack_client)
        self.outport = self.jack_client.outports.register('pulses')
        self.set_rate(jack_client.samplerate)
        self.synth = SimpleSynth(self.rate)

    def jack_process(self, frames: int) -> None:
        buf = memoryview(self.outport.get_buffer()).cast('f')
        self.synth.synth(buf, frames, 440.0, self.power)

    def get_output_controller(self) -> Type["pyeep.outputs.base.OutputController"]:
        return PowerOutputController

    @export
    def set_power(self, power: float):
        self.power = power
