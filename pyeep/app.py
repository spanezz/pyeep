from __future__ import annotations

import argparse
import contextlib
import functools
import sys
import logging
import threading
from queue import Queue
from typing import Callable, IO, Type

try:
    import coloredlogs
    HAVE_COLOREDLOGS = True
except ModuleNotFoundError:
    HAVE_COLOREDLOGS = False

log = logging.getLogger(__name__)


class Component:
    """
    A program component, managed by a Hub, that can send and receive messages
    """
    def __init__(self, *, hub: "Hub", name: str | None = None):
        self.name = name if name is not None else self.__class__.__name__.lower()
        self.logger = logging.getLogger(name)
        self.hub = hub

    def send(self, msg: "Message"):
        """
        Send a message to other components
        """
        msg.src = self
        if self.hub is not None:
            self.hub.send(msg)

    def receive(self, msg: "Message"):
        """
        Function called by the hub to deliver a message to this component
        """
        pass


class Message:
    """
    Base class for messages sent between components
    """
    def __init__(
            self, *,
            src: Component | None = None,
            dst: str | None = None,
            name: str | None = None):
        self.src = src
        self.dst = dst
        if name is None:
            self.name = self.__class__.__name__.lower()
        else:
            self.name = name


class Shutdown(Message):
    """
    Message sent to initiate component shutdown
    """
    pass


class Hub:
    """
    Manage a group of components that share a common technical infrastructure
    """
    # Name of the hub on which to schedule this component
    HUB: str

    def __init__(self, *, app: "App", name: str):
        self.app = app
        self.name = name
        self.components: dict[str, Component] = {}
        self.logger = logging.getLogger(name)

    def start(self):
        """
        Bring the hub components online.

        This can do things like start threads, or schedule asyncio tasks
        """
        pass

    def join(self):
        """
        Cleanup after shutdown.

        This can wait for pending asyncio tasks, or join threads
        """
        pass

    def send(self, msg: Message):
        """
        Called by components to send messages
        """
        if self.app is not None:
            self.app.send(msg)

    def receive(self, msg: Message):
        """
        Called by App to deliver messages to components in this hub

        This is called from the App's thread
        """
        self._hub_thread_receive(msg)

    def _hub_thread_receive(self, msg: Message):
        """
        Called by App to deliver messages to components in this hub

        This is called from the Hub's thread
        """
        self._dispatch_to_components(msg)

    def _dispatch_to_components(self, msg: Message):
        """
        Dispatch a message to the Hub's components
        """
        if msg.dst is None:
            for c in self.components.values():
                c.receive(msg)
        elif (c := self.components.get(msg.dst)) is not None:
            c.receive(msg)

    def add_component(self, component_cls: Type[Component], **kwargs) -> Component:
        """
        Add a new component to this hub
        """
        kwargs["hub"] = self
        component = component_cls(**kwargs)
        self.components[component.name] = component
        return component


class App(contextlib.ExitStack):
    """
    Base application class
    """
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__()
        self.args = args
        self.hubs: dict[str, Hub] = {}
        self.hubs_lock = threading.Lock()
        self.command_queue: Queue[Callable] = Queue()

    @classmethod
    def argparser(cls, description: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="verbose output")
        parser.add_argument("--debug", action="store_true",
                            help="verbose output")
        return parser

    def add_hub(self, hub_cls: Type[Hub], **kwargs):
        """
        Add a new hub to the application
        """
        kwargs["app"] = self
        hub = hub_cls(**kwargs)
        with self.hubs_lock:
            self.hubs[hub.name] = hub

    def remove_hub(self, hub: Hub):
        """
        Remove a hub from the application
        """
        self.command_queue.put(functools.partial(
            self._app_thread_remove_hub, hub))

    def _app_thread_remove_hub(self, hub: Hub):
        """
        Remove a hub from teh application.

        This function is called from the App's thread.
        """
        log.debug("%s: hub shutting down", hub.name)
        with self.hubs_lock:
            self.hubs.pop(hub.name)
        hub.join()

    def add_component(self, component_cls: Type[Component], **kwargs) -> Component:
        """
        Add a new component to the application
        """
        if (hub := self.hubs.get(component_cls.HUB)) is None:
            log.warning(
                "Cannot schedule %s: missing hub %r",
                component_cls.__module__ + "." + component_cls.__qualname__,
                component_cls.HUB)
            return
        return hub.add_component(component_cls, **kwargs)

    def send(self, msg: Message):
        """
        Send a message to the applcation components
        """
        self.command_queue.put(functools.partial(
            self._app_thread_send, msg))

    def _app_thread_send(self, msg: Message):
        """
        Dispatch the message.

        This function is called from the App's thread
        """
        log.debug("Message: %s → %s: %s", msg.src.name if msg.src else "None", msg.dst, msg)
        for hub in self.hubs.values():
            hub.receive(msg)

    def setup_logging(self):
        """
        Set up the logging module for this application
        """
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

    def main_init(self):
        """
        Initialize the application before entering the main loop
        """
        self.setup_logging()
        for hub in self.hubs.values():
            hub.start()

    def main_loop(self):
        """
        Main loop. The application will shut down after this function returns
        """
        while self.hubs:
            try:
                c = self.command_queue.get()
            except KeyboardInterrupt:
                log.info("Keyboard interrupt received: shutting down application")
                self.send(Shutdown())
            else:
                c()

    def main_shutdown(self):
        """
        Shut down the application
        """
        pass

    def main(self):
        self.main_init()
        # self.dump_structure()
        try:
            self.main_loop()
        finally:
            self.main_shutdown()

    def dump_structure(self, file: IO[str] | None = None):
        """
        Print the app structure of hubs and components, for debugging
        """
        for hname, hub in self.hubs.items():
            print(f"{hname} ({hub.__class__.__module__}.{hub.__class__.__name__})", file=file)
            for cname, comp in hub.components.items():
                print(f" - {cname} ({comp.__class__.__module__}.{comp.__class__.__name__})", file=file)
