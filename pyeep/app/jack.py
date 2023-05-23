from __future__ import annotations

import argparse
from . import App

from ..component.jack import Jack


class JackApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_component(Jack, jack_name=self.args.name)

    @classmethod
    def argparser(cls, name: str, description: str) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument("--name", action="store", default=name,
                            help="JACK name to use")
        return parser
