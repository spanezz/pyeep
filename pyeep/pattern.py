import io
from collections.abc import Generator, Iterator
from typing import TYPE_CHECKING, Any

import numpy

from .shape import Shape, Sine
from .volume import Volume

if TYPE_CHECKING:
    from .player import Player


class Pattern:
    """
    Abstract interface for a wave generator
    """

    def __init__(self, description: str | None = None):
        self.player: "Player"
        self.channel_name: str
        self.buffer = io.BytesIO()
        if description is None:
            assert self.__doc__
            self.description = self.__doc__.strip().splitlines()[0].strip()
        else:
            self.description = description
        self.is_silence = False
        self._iter_waves: Iterator[numpy.ndarray] | None = None
        self.current_wave: numpy.ndarray | None = None
        self.read_offset: int = 0
        self.ended: bool = False

    def set_player(self, player: "Player", channel_name: str):
        self.player = player
        self.channel_name = channel_name

    def generate(self) -> Generator[numpy.ndarray]:
        raise NotImplementedError(
            f"{self.__class__.__name__}.generate not implemented"
        )

    def _next_wave(self) -> bool:
        """
        Move self.current_wave to the next wave, or set self.ended if the
        generator is done.

        Returns True if there is a current wave to be read
        """
        if self._iter_waves is None:
            self._iter_waves = iter(self.generate())
        try:
            self.current_wave = next(self._iter_waves)
            self.read_offset = 0
            return True
        except StopIteration:
            self.ended = True
            return False

    def announce(self):
        if self.is_silence:
            return
        self.player.announce_pattern(self)

    def read(self, nsamples: int) -> numpy.ndarray:
        """
        Return an array of at most `nsamples` samples from this pattern.

        If the pattern terminates before the given number of samples, the
        returned array may be shorter than nsamples
        """
        # Shortcut: wave queue is empty
        if self.ended:
            return numpy.empty(0, dtype=self.player.numpy_type)

        if self.current_wave is None:
            if not self._next_wave():
                return numpy.empty(0, dtype=self.player.numpy_type)

        # Shortcut: first wave has enough data
        if len(self.current_wave) >= self.read_offset + nsamples:
            res = self.current_wave[
                self.read_offset : self.read_offset + nsamples
            ]
            self.read_offset += nsamples
            return res

        # Incrementally build a samples array
        res = numpy.empty(0, self.player.numpy_type)
        while (size := nsamples - len(res)) > 0:
            if self.ended:
                # No more waves available
                return res
            elif self.read_offset >= len(self.current_wave):
                # Current wave is exausted, skip to the next one
                self._next_wave()
            else:
                # Take from current wave
                chunk = self.current_wave[
                    self.read_offset : self.read_offset + size
                ]
                self.read_offset += len(chunk)
                res = numpy.append(res, chunk)

        return res

    @property
    def data(self):
        return self.buffer.getvalue()

    def silence(self, *, duration: float) -> numpy.ndarray:
        """
        Generate a silent waveform as a numpy array
        """
        self.player.last_wave_value = None
        self.player.last_volume_value = None
        return numpy.zeros(
            round(duration * self.player.sample_rate),
            dtype=self.player.numpy_type,
        )

    def wave(
        self,
        *,
        shape: float | Shape = 440.0,
        volume: float | Volume = 1.0,
        duration: float = 1.0,
    ) -> numpy.ndarray:
        """
        Generate a waveform as a numpy array
        """
        if not duration:
            return numpy.empty(0, dtype=self.player.numpy_type)

        samples_count = round(duration * self.player.sample_rate)
        x = numpy.arange(samples_count, dtype=self.player.numpy_type)

        match volume:
            case int() | float():
                volume_scaling = float(volume)
                self.player.last_volume_value = volume_scaling
            case Volume():
                volume_scaling = volume.make_array(x, self.player)
                self.player.last_volume_value = volume_scaling[-1]

        match shape:
            case int() | float():
                shape = Sine(freq=shape)

        wave = shape.make_array(x, self.player) * volume_scaling
        self.player.last_wave_value = wave[-1]
        return wave


class Silence(Pattern):
    """
    Silence
    """

    def __init__(self, *, duration: float = 1.0):
        super().__init__(f"{duration:.2f}s of silence")
        self.is_silence = True
        self.duration = duration

    def generate(self) -> Generator[numpy.ndarray]:
        yield self.silence(duration=self.duration)


class Wave(Pattern):
    """
    Simple waveform
    """

    def __init__(
        self,
        *,
        volume: float | Volume = 1.0,
        duration: float = 1.0,
        freq: float = 440.0,
    ):
        """
        Wave `duration` seconds long
        """
        super().__init__(f"wave {duration=:.2f}s {volume=} {freq=}")
        self.volume = volume
        self.duration = duration
        self.freq = freq

    def generate(self) -> Generator[numpy.ndarray]:
        yield self.wave(
            volume=self.volume, duration=self.duration, shape=self.freq
        )


class Waves(Pattern):
    """
    Sum of waves
    """

    def __init__(self, *wargs: dict[str, Any]):
        super().__init__()
        self.wargs = wargs
        last_warg: dict[str, Any] | None = None
        for warg in self.wargs:
            if last_warg is None:
                last_warg = warg
            elif last_warg.get("duration", 1.0) != warg.get("duration", 1.0):
                raise ValueError(
                    f"waves diven of different duration ({last_warg} and {warg}"
                )

    def generate(self) -> Generator[numpy.ndarray]:
        waves: list[numpy.ndarray] = []
        for warg in self.wargs:
            waves.append(self.wave(**warg))
        yield sum(waves)


class PatternSequence(Pattern):
    """
    Pattern that concatenates a generated sequence of Patterns
    """

    def patterns(self) -> Generator[Pattern]:
        raise NotImplementedError(
            f"{self.__class__.__name__}.pattern_sequence not implemented"
        )

    def generate(self) -> Generator[numpy.ndarray]:
        for pattern in self.patterns():
            pattern.set_player(self.player, self.channel_name)
            pattern.announce()
            yield from pattern.generate()
