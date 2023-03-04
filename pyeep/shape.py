from __future__ import annotations

from typing import TYPE_CHECKING

import numpy
import scipy.signal

if TYPE_CHECKING:
    from .player import Player


# References:
# https://stackoverflow.com/questions/64958186/numpy-generate-sine-wave-signal-with-time-varying-frequency
# https://scialicia.com/2018/08/python-frequency-modulation-with-numpy/
# https://en.wikipedia.org/wiki/Frequency_modulation_synthesis
# https://en.wikipedia.org/wiki/Frequency_modulation
# http://hplgit.github.io/primer.html/doc/pub/diffeq/._diffeq-solarized002.html
# https://dsp.stackexchange.com/questions/81140/how-can-i-generate-a-sine-wave-with-time-varying-frequency-that-is-continuous-in


class Shape:
    """
    Shape of a waveform
    """
    def __repr__(self):
        return self.__str__()

    def make_array(self, x: numpy.ndarray, player: Player) -> numpy.ndarray:
        raise NotImplementedError(f"{self.__class__.__name__}.make_array not implemented")


class Sine(Shape):
    """
    Sine wave with a given frequency
    """
    def __init__(self, freq: float):
        self.freq = float(freq)

    def make_array(self, x: numpy.ndarray, player: Player) -> numpy.ndarray:
        if player.last_wave_value is not None:
            sync_factor = numpy.arcsin(player.last_wave_value)
        else:
            sync_factor = 0.0

        factor = self.freq * 2.0 * numpy.pi / player.sample_rate
        return numpy.sin(x * factor + sync_factor)


class Chirp(Shape):
    """
    Wrapper around scipy.signal.chirp
    """
    # https://en.wikipedia.org/wiki/Chirp
    # FIXME: use https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.chirp.html ?
    def __init__(
            self,
            f0: float = 440.0,
            f1: float = 880.0,
            method: str = "linear"):
        self.f0 = float(f0)
        self.f1 = float(f1)
        self.method = method

    def __str__(self):
        return f"Chirp({self.f0}-{self.f1}, {self.method})"

    def make_array(self, x: numpy.ndarray, player: Player) -> numpy.ndarray:
        """
        Compute the volume scaling factor function (from 0 to 1) corresponding
        to the given array (generally generated with `arange(samples_count)`)
        """
        if player.last_wave_value is not None:
            sync_factor = numpy.arcsin(player.last_wave_value)
        else:
            sync_factor = 0.0

        # c = (self.f2 - self.f1) * player.sample_rate / len(x)
        # t = x / player.sample_rate
        # return numpy.sin(sync_factor + 2.0 * numpy.pi * (c / 2 * t*t + self.f1 * t))

        t = x / player.sample_rate
        return scipy.signal.chirp(
                t,
                f0=self.f0, f1=self.f1,
                t1=len(x) / player.sample_rate,
                method=self.method,
                phi=sync_factor)
