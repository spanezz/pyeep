from __future__ import annotations

import threading

import pylsl

from .app import Message
from .aio import AIOComponent


class LSLSamples(Message):
    def __init__(self, samples: list, timestamps: list):
        super().__init__()
        self.samples = samples
        self.timestamps = timestamps


class LSLComponent(AIOComponent):
    def __init__(self, *, stream_type: str, max_samples: int = 256, **kwargs):
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.HUB + "_" + self.name, target=self.thread_run)
        self.stream_type = stream_type
        self.max_samples = max_samples
        self.thread_stop = False
        self.thread.start()

    def cleanup(self):
        """
        Cleanup/release resources before this component is removed
        """
        self.thread_stop = True
        self.thread.join()

    def thread_run(self):
        self.logger.info("connecting to stream inlet")
        self.info = pylsl.resolve_stream('type', self.stream_type)[0]
        self.inlet = pylsl.StreamInlet(self.info)
        self.logger.info("connected to stream inlet")

        while not self.thread_stop:
            samples, timestamps = self.inlet.pull_chunk(timeout=0.2, max_samples=self.max_samples)
            if not samples:
                continue
            if not self.hub.loop:
                continue
            self.hub.loop.call_soon_threadsafe(self.receive, LSLSamples(samples=samples, timestamps=timestamps))

        # self.inlet.close_stream()
