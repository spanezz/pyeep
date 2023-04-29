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
        self.stream_info: pylsl.StreamInfo | None = None
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
        while not self.stream_info and not self.thread_stop:
            # We need a high timeout or it can fail to connect in time even if the
            # stream exists
            info = pylsl.resolve_byprop(prop='type', value=self.stream_type, timeout=2)
            if info:
                self.stream_info = info[0]

        if self.thread_stop:
            return

        self.inlet = pylsl.StreamInlet(self.stream_info)
        self.logger.info("connected to stream inlet")

        while not self.thread_stop:
            samples, timestamps = self.inlet.pull_chunk(timeout=0.2, max_samples=self.max_samples)
            if not samples:
                continue
            if not self.hub.loop:
                continue
            self.hub.loop.call_soon_threadsafe(self.receive, LSLSamples(samples=samples, timestamps=timestamps))

        # self.inlet.close_stream()
