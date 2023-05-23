from __future__ import annotations

import threading

import jack

from ..messages import NewComponent, Shutdown
from .base import Component
from .aio import AIOComponent


class JackComponent(Component):
    """
    Component that gets called by the JACK realtime process function
    """
    def jack_process(self, frames: int):
        """
        JACK process function, running in JACK's realtime thread
        """
        raise NotImplementedError(f"{self.__class__.__name__}.jack_process not implemented")


class Jack(AIOComponent):
    def __init__(self, jack_name: str, **kwargs):
        super().__init__(**kwargs)
        self.jack_name = jack_name
        self.jack_client = jack.Client(self.jack_name)
        self.jack_client.set_process_callback(self.jack_process)
        self.samplerate = self.jack_client.samplerate
        self.jack_components: list["JackComponent"] = []
        self.jack_components_lock = threading.Lock()

    def jack_process(self, frames: int):
        """
        JACK process function, running in JACK's realtime thread
        """
        with self.jack_components_lock:
            for c in self.jack_components:
                c.jack_process(frames)

    def add_jack_component(self, component: JackComponent) -> None:
        """
        Add a JACK component to be called in the JACK process function.

        The function is idempotent: adding a comnponent multiple times is the
        same as adding it only once
        """
        with self.jack_components_lock:
            if component not in self.process_callbacks:
                self.process_callbacks.append(component)

    def remove_jack_component(self, component: JackComponent) -> None:
        """
        Remove a JACK component.

        If the comnponent is not present, nothing will happen
        """
        with self.process_callbacks_lock:
            try:
                self.jack_components.remove(component)
            except ValueError:
                pass

    async def run(self) -> None:
        """
        Main body of this component
        """
        with self.jack_client:
            while True:
                match (msg := await self.next_message()):
                    case Shutdown():
                        break
                    case NewComponent():
                        if isinstance(msg.src, JackComponent):
                            self.add_jack_component(msg.src)
