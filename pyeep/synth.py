from __future__ import annotations

import math

import numba
import numpy
from numba.experimental import jitclass


@jitclass([
    ("rate", numba.int32),
    ("phase", numba.float64),
])
class SineWave:
    """
    Phase accumulation synthesis
    """
    # See https://www.gkbrk.com/wiki/PhaseAccumulator/

    def __init__(self, rate: int):
        self.rate: int = rate
        self.phase: float = 0.0

    def skip(self, frames: int, freq: float):
        self.phase = (self.phase + frames * 2.0 * math.pi * freq / self.rate) % (2 * math.pi)

    def wave(self, array: numpy.ndarray, freq: float) -> None:
        for i in range(len(array)):
            self.phase = (self.phase + 2.0 * math.pi * freq / self.rate) % (2 * math.pi)
            array[i] += math.sin(self.phase)

    def synth(self, array: numpy.ndarray, freq: float, envelope: numpy.ndarray) -> None:
        for i in range(len(array)):
            self.phase = (self.phase + 2.0 * math.pi * freq / self.rate) % (2 * math.pi)
            array[i] += math.sin(self.phase) * envelope[i]


@jitclass([
    ("rate", numba.int32),
    ("phase", numba.float64),
])
class SawWave:
    """
    Phase accumulation synthesis
    """
    # See https://www.gkbrk.com/wiki/PhaseAccumulator/

    def __init__(self, rate: int):
        self.rate: int = rate
        self.phase: float = 0.0

    def synth(self, array: numpy.ndarray, freq: float, envelope: numpy.ndarray) -> None:
        for i in range(len(array)):
            self.phase = (self.phase + freq / self.rate) % 2
            array[i] += (1 - self.phase) * envelope[i]


@jitclass([
    ("attack_level", numba.float64),
    ("attack_time", numba.float64),
    ("decay_time", numba.float64),
    ("sustain_level", numba.float64),
    ("release_time", numba.float64),
])
class EnvelopeShape:
    def __init__(
            self,
            attack_level: float = 1.0,
            attack_time: float = 0.1,
            decay_time: float = 0.2,
            sustain_level: float = 0.9,
            release_time: float = 0.2):
        self.attack_level = attack_level
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.sustain_level = sustain_level
        self.release_time = release_time


@jitclass([
    ("start_frame", numba.int32),
    ("rate", numba.int32),
    ("velocity", numba.float64),
    ("sustain_start", numba.int32),
    ("release_frames", numba.int32),
    ("release_start", numba.int32),
    ("head", numba.float64[:]),
    ("tail", numba.float64[:]),
])
class Envelope:
    shape: EnvelopeShape

    def __init__(
            self,
            shape: EnvelopeShape,
            frame_time: int,
            rate: int,
            start_level: float = 0.0,
            velocity: float = 1.0):
        self.shape = shape
        self.start_frame = frame_time
        self.rate = rate
        self.velocity = velocity
        self.sustain_start = round((self.shape.attack_time + self.shape.decay_time) * rate)
        self.release_frames = round(self.shape.release_time * rate)
        self.release_start: int = 0
        # Precomputed lead values
        self.head = numpy.concatenate((
                numpy.linspace(
                    start_level, self.shape.attack_level * velocity,
                    round(self.shape.attack_time * rate)),
                numpy.linspace(
                    self.shape.attack_level * velocity, self.shape.sustain_level * velocity,
                    round(self.shape.decay_time * rate))))
        self.tail: numpy.zeros(1)

    def release(self, frame_time: int) -> None:
        """
        Notify of the instrument release
        """
        self.release_start = frame_time - self.start_frame
        elapsed = frame_time - self.start_frame
        if elapsed < len(self.head):
            # Release happened during the attack/decay phase
            start_level = self.head[elapsed]
        else:
            # Release happened during the sustain phase
            start_level = self.shape.sustain_level * self.velocity
        self.tail = numpy.linspace(start_level, 0, self.release_frames)

    def get_chunk(self, frame_time: int, frames: int) -> numpy.ndarray | None:
        elapsed = frame_time - self.start_frame
        # print(f"get_chunk {frame_time=} {frames=} {elapsed=}")

        if self.release_start > 0 and elapsed >= self.release_start:
            if elapsed >= self.release_start + len(self.tail):
                # Silence after release
                # print("  post-r")
                return None
            else:
                # Release
                offset = elapsed - self.release_start
                size = min(frames, len(self.tail))
                # print(f"  r {offset=} {size=}")
                return self.tail[offset:offset + size]
        elif elapsed >= len(self.head):
            # Sustain
            if self.release_start == 0:
                count = frames
            else:
                count = min(frames, self.release_start - elapsed)
            # print(f"  s {count=}")
            return numpy.full(count, self.shape.sustain_level * self.velocity)
        else:
            # Attack/decay
            size = min(frames, len(self.head))
            if self.release_start > 0:
                size = min(size, self.release_start - elapsed)
            # print(f"  ad {elapsed=} {size=}")
            return self.head[elapsed:elapsed + size]

    def generate(self, frame_time: int, frames: int) -> numpy.ndarray | None:
        res = numpy.zeros(frames)
        start = 0
        has_data = False

        while start < frames:
            chunk = self.get_chunk(frame_time + start, frames - start)
            if chunk is None:
                if not has_data:
                    return None
                chunk = numpy.zeros(frames - start)
            else:
                has_data = True
            res[start:start+len(chunk)] = chunk
            start += len(chunk)

        return res
