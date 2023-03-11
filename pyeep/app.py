from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import logging
import threading
from typing import Type, TypeVar

import jack
from .jackmidi import JackComponent

try:
    import coloredlogs
    HAVE_COLOREDLOGS = True
except ModuleNotFoundError:
    HAVE_COLOREDLOGS = False


class App(contextlib.ExitStack):
    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.shutting_down = False

    @classmethod
    def argparser(cls, description: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="verbose output")
        parser.add_argument("--debug", action="store_true",
                            help="verbose output")
        return parser

    def shutdown(self):
        self.shutting_down = True

    def setup_logging(self):
        FORMAT = "%(levelname)s %(name)s %(message)s"
        if self.args.debug:
            log_level = logging.DEBUG
        elif self.args.verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        if coloredlogs is not None:
            coloredlogs.install(level=log_level, fmt=FORMAT)
        else:
            logging.basicConfig(level=log_level, stream=sys.stderr, format=FORMAT)

    async def aio_main(self):
        pass

    def ui_main(self):
        pass

    def _aio_thread(self):
        asyncio.run(self.aio_main())

    def main_init(self):
        self.setup_logging()

    def main(self):
        self.main_init()
        aio_thread = threading.Thread(target=self._aio_thread, name="aio")
        aio_thread.start()
        try:
            self.ui_main()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
            aio_thread.join()


AppJackComponent = TypeVar("AppJackComponent", bound=JackComponent)


class JackApp(App):
    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
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
