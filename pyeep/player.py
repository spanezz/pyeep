from __future__ import annotations

from typing import TYPE_CHECKING

import numpy

from pyeep.component.aio import AIOComponent
from pyeep.messages import Shutdown

if TYPE_CHECKING:
    from .pattern import Pattern


class Player(AIOComponent):
    """
    Abstract base infrastructure for an pattern player
    """

    def __init__(self, *, sample_rate: int = 44100, numpy_type=numpy.float32, **kwargs):
        super().__init__(**kwargs)
        # sampling rate, Hz, must be integer
        self.sample_rate = sample_rate
        # TODO: replace with a dict (and exploit its ordering properties)
        self.channels: list[Pattern] = []
        self.overrides: list[Pattern] = []
        self.numpy_type = numpy_type
        # See https://stackoverflow.com/questions/42192239/remove-control-clicking-sound-using-pyaudio-as-an-oscillator
        # This is used to seamlessly join consecutive waveforms
        self.last_wave_value: float | None = None
        self.last_volume_value: float | None = None

    def receive(self, msg):
        # FIXME: hacky compatibility layer until this is refactored into a component
        if isinstance(msg, Shutdown):
            self.shutdown()
        super().receive(msg)

    def start_mono(self, pattern: Pattern):
        """
        Start playing the given pattern as mono output
        """
        pattern.set_player(self, "mono")
        pattern.announce()
        self.channels.append(pattern)
        self.overrides.append(None)

    def start_stereo(self, left: Pattern, right: Pattern):
        """
        Start playing the given patterns as stereo output
        """
        left.set_player(self, "left")
        left.announce()
        self.channels.append(left)
        self.overrides.append(None)
        right.set_player(self, "right")
        right.announce()
        self.channels.append(right)
        self.overrides.append(None)

    def announce_pattern(self, pattern: Pattern) -> None:
        print("〜", pattern.channel_name, pattern.description)

    def set_override(self, channel_name: str, pattern: Pattern, replace: bool = False):
        """
        Set a pattern to temporarily suspend the one for the current channel
        and play instead.

        The current pattern will resume once the overriding pattern terminates.

        If `replace` is True, an existing override will be replaced.
        """
        if channel_name in ("mono", "left"):
            index = 0
        elif channel_name == "right":
            index = 1

        if self.overrides[index] is None or replace:
            pattern.set_player(self, channel_name)
            self.overrides[index] = pattern
            pattern.announce()

    def get_samples(self, frame_count: int) -> numpy.ndarray:
        """
        Get the next `frame_count` frames of audio data to be played
        """
        # See https://stackoverflow.com/questions/5347065/interweaving-two-numpy-arrays
        if len(self.channels) == 1:
            # Shortcut for mono output
            if self.overrides[0] is not None:
                wave = self.overrides[0].read(frame_count)
                if wave.size < frame_count:
                    self.overrides[0] = None
            else:
                wave = self.channels[0].read(frame_count)
            if wave.size < frame_count:
                # Pad with silence
                wave.resize(frame_count)
            return wave

        # General case for an arbitrary number of channels
        waves = numpy.empty(frame_count * len(self.channels), dtype=self.numpy_type)
        for idx, channel in enumerate(self.channels):
            if self.overrides[idx] is not None:
                wave = self.overrides[idx].read(frame_count)
                if wave.size < frame_count:
                    self.overrides[idx] = None
            else:
                wave = self.channels[idx].read(frame_count)
            if wave.size < frame_count:
                # Pad with silence
                wave.resize(frame_count)
            waves[idx::len(self.channels)] = wave
        return waves

    async def run(self):
        """
        Player main loop
        """
        pass
