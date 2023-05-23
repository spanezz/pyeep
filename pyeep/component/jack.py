from __future__ import annotations

import jack

from ..messages import Shutdown
from .aio import AIOComponent


class Jack(AIOComponent):
    def __init__(self, jack_name: str, **kwargs):
        super().__init__(**kwargs)
        self.jack_name = jack_name
        self.jack_client = jack.Client(self.jack_name)
        self.jack_client.set_process_callback(self.on_process)
        self.samplerate = self.jack_client.samplerate

    def on_process(self, frames: int):
        """
        JACK process function, running in JACK's realtime thread
        """
        raise NotImplementedError(f"{self.__class__.__name__}.on_process not implemented")
    # def on_process(self, frames: int):
    #     for c in self.components.values():
    #         c.on_process(frames)

    async def run(self) -> None:
        """
        Main body of this component
        """
        with self.jack_client:
            while True:
                match await self.next_message():
                    case Shutdown():
                        break
