from __future__ import annotations

import argparse
import contextlib
import sys
import logging
import threading

try:
    import coloredlogs
    HAVE_COLOREDLOGS = True
except ModuleNotFoundError:
    HAVE_COLOREDLOGS = False

log = logging.getLogger(__name__)


class Component:
    def __init__(self, *, name: str | None = None):
        self.name = name if name is not None else self.__class__.__name__.lower()
        self.logger = logging.getLogger(name)
        self.hub: "Hub" | None = None
        self.shutting_down = False

    def shutdown(self):
        self.shutting_down = True

    def send(self, msg: "Message"):
        msg.src = self
        if self.hub is not None:
            self.hub.send(msg)

    def receive(self, msg: "Message"):
        pass


class Message:
    def __init__(self, *, src: Component | None = None, dst: str | None = None):
        self.src = src
        self.dst = dst


class Shutdown(Message):
    pass


class Hub:
    def __init__(self, name: str):
        self.name = name
        self.app: "App" | None = None
        self.components: dict[str, Component] = {}

    def start(self):
        pass

    def join(self):
        pass

    def send(self, msg: Message):
        if self.app is not None:
            self.app.send(msg)

    def receive(self, msg: Message):
        if msg.dst is None:
            for c in self.components.values():
                c.receive(msg)
        elif (c := self.components.get(msg.dst)) is not None:
            c.receive(msg)

    def add_component(self, component: Component) -> bool:
        return False

    def shutdown(self):
        for c in self.components.values():
            c.shutdown()


class ThreadHub(Hub):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.thread = threading.Thread(name=name, target=self.run)

    def start(self):
        super().start()
        self.thread.start()

    def join(self):
        super().join()
        self.thread.join()

    def run(self):
        raise NotImplementedError("ThreadHub.run")


class App(contextlib.ExitStack):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__()
        self.args = args
        self.shutting_down = False
        self.hubs: dict[str, Hub] = {}

    @classmethod
    def argparser(cls, description: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="verbose output")
        parser.add_argument("--debug", action="store_true",
                            help="verbose output")
        return parser

    def add_hub(self, hub: Hub):
        hub.app = self
        self.hubs[hub.name] = hub

    def add_component(self, component: Component):
        for hub in self.hubs.values():
            if hub.add_component(component):
                break
        else:
            log.error("%s: component not claimed by any threads", component.name)

    def send(self, msg: Message):
        log.debug("%s → %s: %s", msg.src.name if msg.src else "None", msg.dst, msg)
        for hub in self.hubs.values():
            hub.receive(msg)

    def shutdown(self):
        self.send(Shutdown())
        self.shutting_down = True
        for hub in self.hubs.values():
            hub.shutdown()
        for hub in self.hubs.values():
            hub.join()

    def setup_logging(self):
        FORMAT = "%(levelname)s %(name)s %(message)s"
        if self.args.debug:
            log_level = logging.DEBUG
        elif self.args.verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        if HAVE_COLOREDLOGS:
            coloredlogs.install(level=log_level, fmt=FORMAT)
        else:
            logging.basicConfig(level=log_level, stream=sys.stderr, format=FORMAT)

    def main_loop(self):
        pass

    def main_init(self):
        self.setup_logging()
        for hub in self.hubs.values():
            hub.start()

    def main(self):
        self.main_init()
        try:
            self.main_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
