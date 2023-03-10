from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from typing import Optional

import pyaudio

from .player import Player

log = logging.getLogger(__name__)


@contextlib.contextmanager
def silence_output():
    """
    Temporarily redirect stdout and stderr to /dev/null
    """
    # See https://stackoverflow.com/questions/67765911/how-do-i-silence-pyaudios-noisy-output
    null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
    save_fds = [os.dup(1), os.dup(2)]

    try:
        os.dup2(null_fds[0], 1)
        os.dup2(null_fds[1], 2)

        yield
    finally:
        os.dup2(save_fds[0], 1)
        os.dup2(save_fds[1], 2)

        for fd in null_fds:
            os.close(fd)


class PyAudioPlayer(Player, threading.Thread):
    """
    Play patterns on a sound device using PyAudio
    """
    def __init__(self) -> None:
        super().__init__()
        with silence_output():
            self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.shutting_down = False

    async def wait_for_patterns(self):
        while not self.shutting_down and not all(c.ended for c in self.channels):
            await asyncio.sleep(0.2)

    async def loop(self):
        self.start()
        await self.wait_for_patterns()

    def shutdown(self):
        log.info("Shutting down")
        self.shutting_down = True
        if self.stream:
            while self.stream.is_active():
                time.sleep(0.1)
            self.stream.stop_stream()
            self.stream.close()
        self.join()

        self.audio.terminate()

    def _stream_callback(self, in_data, frame_count: int, time_info, status) -> tuple[bytes, int]:
        if self.shutting_down:
            return bytes(), pyaudio.paComplete
        return self.get_samples(frame_count).tobytes(), pyaudio.paContinue

    def run(self):
        # for paFloat32 sample values must be in range [-1.0, 1.0]
        self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=len(self.channels),
                rate=self.sample_rate,
                output=True,
                # See https://stackoverflow.com/questions/31391766/pyaudio-outputs-slow-crackling-garbled-audio
                frames_per_buffer=4096,
                stream_callback=self._stream_callback)
