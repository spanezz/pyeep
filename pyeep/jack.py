from __future__ import annotations

import argparse
import contextlib
from typing import Type

import jack

from .app import Component, App, Hub


class JackComponent(Component):
    def __init__(self, jack_client: jack.Client, **kwargs):
        super().__init__(**kwargs)
        self.jack_client = jack_client
        self.samplerate = self.jack_client.samplerate

    def on_process(self, frames: int):
        raise NotImplementedError(f"{self.__class__.__name__}.on_process not implemented")


class JackHub(Hub):
    def __init__(self, jack_name: str):
        super().__init__(name="JACK")
        self.jack_client = jack.Client(jack_name)
        self.jack_client.set_process_callback(self.on_process)
        self.stack = contextlib.ExitStack()

    def start(self):
        self.stack.enter_context(self.jack_client)
        super().start()

    def shutdown(self):
        super().shutdown()
        self.stack.close()

    def add_component(self, component_cls: Type[Component], **kwargs) -> Component:
        if issubclass(component_cls, JackComponent):
            kwargs["hub"] = self
            kwargs["jack_client"] = self.jack_client
            component = component_cls(**kwargs)
            self.components[component.name] = component
            return component

        return super().add_component(component_cls, **kwargs)

    def on_process(self, frames: int):
        for c in self.components.values():
            c.on_process(frames)


class JackApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_hub(JackHub(jack_name=self.args.name))

    @classmethod
    def argparser(cls, name: str, description: str) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument("--name", action="store", default=name,
                            help="JACK name to use")
        return parser
