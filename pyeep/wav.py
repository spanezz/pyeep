from __future__ import annotations

import wave

import numpy

from .player import Player


class WaveWriter(Player):
    """
    Player that writes audio data to a .wav audio file
    """
    def __init__(self, filename: str):
        super().__init__()
        self.wav = wave.open(filename, "wb")

    async def loop(self):
        self.wav.setnchannels(len(self.channels))
        self.wav.setsampwidth(1)
        self.wav.setframerate(self.sample_rate)
        while True:
            samples = self.get_samples(self.sample_rate)
            data = (samples * 128 + 128).astype(numpy.int8).tobytes()
            self.wav.writeframesraw(data)
            if all(c.ended for c in self.channels):
                break

    def shutdown(self):
        self.wav.close()
