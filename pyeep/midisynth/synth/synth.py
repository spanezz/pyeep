import abc
import math
from collections.abc import Callable
from typing import Any, override

import numpy as np

try:
    import numba
    from numba import jit
    from numba.experimental import jitclass

    phase_accumulator_spec = [("rate", numba.int32), ("phase", numba.float64)]
except ModuleNotFoundError:

    def jit[T](*args: Any, **kwargs: Any) -> Callable[[T], T]:
        def wrapper(value: T) -> T:
            return value

        return wrapper

    def jitclass[T](*args: Any, **kwargs: Any) -> Callable[[T], T]:
        def wrapper(value: T) -> T:
            return value

        return wrapper

    phase_accumulator_spec = []

type WaveArray = np.ndarray[tuple[int], np.dtype[np.float64]]


@jitclass(phase_accumulator_spec)
class PhaseAccumulator:
    """Phase accumulator for wave generation."""

    def __init__(self, rate: int) -> None:
        self.rate = rate
        self.phase: float = 0.0

    def advance(self, frames: int, freq: float) -> None:
        """
        Advance the phase.

        :param frames: number of frames to advance
        :param freq: wave frequency
        """
        self.phase = (
            self.phase + frames * 2.0 * math.pi * freq / self.rate
        ) % (2 * math.pi)


class Wave(abc.ABC):
    """Base class for wave synthesizers."""

    def __init__(self, rate: int) -> None:
        """
        Initialize a Wave.

        :param rate: sampling rate in samples per second.
        """
        self.rate = rate

    @abc.abstractmethod
    def wave(self, array: WaveArray, freq: float) -> None:
        """
        Generate a wave at full amplitude.

        :param array: array where generated data is stored. The length of the
          array is used for the number of frames to generate
        :param freq: frequency of the wave
        """

    @abc.abstractmethod
    def synth(
        self,
        array: WaveArray,
        freq: float,
        envelope: WaveArray,
    ) -> None:
        """
        Generate a wave with an amplitude envelope.

        :param array: array where generated data is stored. The length of the
          array is used for the number of frames to generate
        :param freq: frequency of the wave
        :param envelope: amplitude envelope to apply to the wave
        """


class PhaseAccumulationWave(Wave):
    """Phase-accumulation wave synthesis."""

    # See https://www.gkbrk.com/wiki/PhaseAccumulator/

    def __init__(self, rate: int) -> None:
        super().__init__(rate)
        self.phase = PhaseAccumulator(self.rate)

    def skip(self, frames: int, freq: float) -> None:
        """
        Simulate generating a portion of the wave.

        :param frames: number of frames to simulate
        :param freq: wave frequency to simulate
        """
        self.phase.advance(frames, freq)


@jit(nopython=True)
def synth_sine(
    phase: PhaseAccumulator, out: WaveArray, freq: float, envelope: WaveArray
) -> None:
    for i in range(len(out)):
        out[i] += math.sin(phase.phase) * envelope[i]
        phase.advance(1, freq)


class SineWave(PhaseAccumulationWave):
    """
    Phase accumulation synthesis
    """

    @override
    def wave(self, array: WaveArray, freq: float) -> None:
        for i in range(len(array)):
            array[i] += math.sin(self.phase.phase)
            self.phase.advance(1, freq)

    @override
    def synth(
        self,
        array: WaveArray,
        freq: float,
        envelope: WaveArray,
    ) -> None:
        synth_sine(self.phase, array, freq, envelope)


@jit(nopython=True)
def synth_saw(
    phase: PhaseAccumulator, out: WaveArray, freq: float, envelope: WaveArray
) -> None:
    for i in range(len(out)):
        out[i] += phase.phase / (2 * math.pi) * envelope[i]
        phase.advance(1, freq)


class SawWave(PhaseAccumulationWave):
    """
    Phase accumulation synthesis
    """

    @override
    def wave(self, array: WaveArray, freq: float) -> None:
        for i in range(len(array)):
            array[i] += self.phase.phase / (2 * math.pi)
            self.phase.advance(1, freq)

    @override
    def synth(self, array: WaveArray, freq: float, envelope: WaveArray) -> None:
        synth_saw(self.phase, array, freq, envelope)


class EnvelopeShape:
    def __init__(
        self,
        attack_level: float = 1.0,
        attack_time: float = 0.1,
        decay_time: float = 0.2,
        sustain_level: float = 0.9,
        release_time: float = 0.2,
    ):
        self.attack_level = attack_level
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.sustain_level = sustain_level
        self.release_time = release_time


class Envelope:
    """Generate amplitude envelopes."""

    shape: EnvelopeShape

    def __init__(
        self,
        shape: EnvelopeShape,
        frame_time: int,
        rate: int,
        start_level: float = 0.0,
        velocity: float = 1.0,
    ) -> None:
        self.shape = shape
        self.start_frame = frame_time
        self.rate = rate
        self.velocity = velocity
        self.sustain_start = round(
            (self.shape.attack_time + self.shape.decay_time) * rate
        )
        self.release_frames = round(self.shape.release_time * rate)
        self.release_start: int = 0
        # Precomputed lead values
        self.head: WaveArray = np.concatenate(
            (
                np.linspace(
                    start_level,
                    self.shape.attack_level * velocity,
                    round(self.shape.attack_time * rate),
                    dtype=np.float64,
                ),
                np.linspace(
                    self.shape.attack_level * velocity,
                    self.shape.sustain_level * velocity,
                    round(self.shape.decay_time * rate),
                    dtype=np.float64,
                ),
            )
        )
        self.tail: WaveArray = np.zeros(1)

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
        self.tail = np.linspace(start_level, 0, self.release_frames)

    def get_chunk(self, frame_time: int, frames: int) -> WaveArray | None:
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
                return self.tail[offset : offset + size]
        elif elapsed >= len(self.head):
            # Sustain
            if self.release_start == 0:
                count = frames
            else:
                count = min(frames, self.release_start - elapsed)
            # print(f"  s {count=}")
            return np.full(count, self.shape.sustain_level * self.velocity)
        else:
            # Attack/decay
            size = min(frames, len(self.head))
            if self.release_start > 0:
                size = min(size, self.release_start - elapsed)
            # print(f"  ad {elapsed=} {size=}")
            return self.head[elapsed : elapsed + size]

    def generate(self, frame_time: int, frames: int) -> WaveArray | None:
        res = np.zeros(frames)
        start = 0
        has_data = False

        while start < frames:
            chunk = self.get_chunk(frame_time + start, frames - start)
            if chunk is None:
                if not has_data:
                    return None
                chunk = np.zeros(frames - start)
            else:
                has_data = True
            res[start : start + len(chunk)] = chunk
            start += len(chunk)

        return res
