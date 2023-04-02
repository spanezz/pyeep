from __future__ import annotations

import argparse
from typing import Type, TypeVar

import jack

from .app import Component, App


class JackComponent(Component):
    def __init__(self, client: jack.Client):
        super().__init__()
        self.client = client
        self.samplerate = self.client.samplerate

    def on_process(self, frames: int):
        raise NotImplementedError(f"{self.__class__.__name__}.on_process not implemented")


AppJackComponent = TypeVar("AppJackComponent", bound=JackComponent)


class JackApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.jack_client = jack.Client(self.args.name)
        self.jack_client.set_process_callback(self.on_process)
        self.jack_components: list[JackComponent] = []

    def add_jack_component(self, cls: Type[AppJackComponent], **kwargs) -> JackComponent:
        component = cls(self.jack_client, **kwargs)
        self.jack_components.append(component)
        return component

    def on_process(self, frames: int):
        for c in self.jack_components:
            c.on_process(frames)

    def main_init(self):
        super().main_init()
        self.enter_context(self.jack_client)

    @classmethod
    def argparser(cls, name: str, description: str) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument("--name", action="store", default=name,
                            help="JACK name to use")
        return parser
