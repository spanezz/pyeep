from __future__ import annotations

import argparse
import contextlib
from typing import Any

import jack

from .app import App, Component, Hub, Message


class JackComponent(Component):
    HUB = "jack"

    def __init__(self, jack_client: jack.Client, **kwargs):
        super().__init__(**kwargs)
        self.jack_client = jack_client
        self.samplerate = self.jack_client.samplerate

    def on_process(self, frames: int):
        raise NotImplementedError(f"{self.__class__.__name__}.on_process not implemented")


class JackHub(Hub):
    def __init__(self, jack_name: str, **kwargs):
        kwargs.setdefault("name", "jack")
        super().__init__(**kwargs)
        self.jack_client = jack.Client(jack_name)
        self.jack_client.set_process_callback(self.on_process)
        self.stack = contextlib.ExitStack()

    def start(self):
        super().start()
        self.stack.enter_context(self.jack_client)

    def join(self):
        self.stack.close()
        super().join()

    def _hub_thread_receive(self, msg: Message):
        super()._hub_thread_receive(msg)
        if msg.name == "shutdown":
            self.app.remove_hub(self)

    def fill_component_kwargs(self, kwargs: dict[str, Any]):
        super().fill_component_kwargs(kwargs)
        kwargs["jack_client"] = self.jack_client

    def on_process(self, frames: int):
        for c in self.components.values():
            c.on_process(frames)


class JackApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_hub(JackHub, jack_name=self.args.name)

    @classmethod
    def argparser(cls, name: str, description: str) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument("--name", action="store", default=name,
                            help="JACK name to use")
        return parser
