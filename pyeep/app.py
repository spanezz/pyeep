from __future__ import annotations

import argparse
import contextlib
import functools
import sys
import logging
import threading
from queue import SimpleQueue
from typing import Any, Callable, IO, Type

try:
    import coloredlogs
    HAVE_COLOREDLOGS = True
except ModuleNotFoundError:
    HAVE_COLOREDLOGS = False

log = logging.getLogger(__name__)


def check_hub(f):
    """
    Dectorator enforcing that a function is run in the context of the specific
    hub
    """
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.hub._running_in_hub():
            raise RuntimeError(f"function for hub {self.HUB} run outside of the hub context")
        return f(self, *args, **kwargs)
    return wrapper


class Component:
    """
    A program component, managed by a Hub, that can send and receive messages
    """
    def __init__(self, *, hub: "Hub", name: str | None = None):
        self.name = name if name is not None else self.__class__.__name__.lower()
        self.logger = logging.getLogger(self.name)
        self.hub = hub

    def __str__(self) -> str:
        return self.name

    @check_hub
    def cleanup(self):
        """
        Cleanup/release resources before this component is removed
        """
        pass

    @check_hub
    def send(self, msg: "Message"):
        """
        Send a message to other components
        """
        msg.src = self
        if self.hub is not None:
            self.hub.send(msg)

    @check_hub
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

    def __str__(self) -> str:
        return self.name


class Shutdown(Message):
    """
    Message sent to initiate component shutdown
    """
    pass


class Hub:
    """
    Manage a group of components that share a common technical infrastructure
    """
    # Name of this hub
    HUB: str

    def __init__(self, *, app: "App"):
        self.app = app
        self.hub = self
        self.components: dict[str, Component] = {}
        self.logger = logging.getLogger(self.HUB)

    def __str__(self) -> str:
        return f"Hub({self.HUB})"

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

    def _running_in_hub(self) -> bool:
        """
        Check if we're running in the context of this hub
        """
        raise NotImplementedError(f"{self.__class__.__name__}._running_in_hub")

    @check_hub
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

    @check_hub
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
            for c in list(self.components.values()):
                c.receive(msg)
        elif (c := self.components.get(msg.dst)) is not None:
            c.receive(msg)

    def fill_component_kwargs(self, kwargs: dict[str, Any]):
        """
        Perform dependency injection on newly created components for this hub,
        by adding keyword arguments to their constructor
        """
        kwargs["hub"] = self

    def add_component(self, component: Component):
        """
        Add a new component to this hub
        """
        self._hub_thread_add_component(component)

    @check_hub
    def _hub_thread_add_component(self, component):
        self.components[component.name] = component
        self.logger.debug("new component %r", component.name)

    def remove_component(self, component: Component):
        """
        Remove the component from this hub
        """
        self._hub_thread_remove_component(component)

    @check_hub
    def _hub_thread_remove_component(self, component):
        component.cleanup()
        del self.components[component.name]
        self.logger.debug("removed component %r", component.name)


class App(contextlib.ExitStack):
    """
    Base application class
    """
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__()
        self.args = args
        self.hubs: dict[str, Hub] = {}
        self.hubs_lock = threading.Lock()
        self.command_queue: SimpleQueue[Callable] = SimpleQueue()

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
            self.hubs[hub.HUB] = hub

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
        log.debug("%s: hub shutting down", hub.HUB)
        with self.hubs_lock:
            self.hubs.pop(hub.HUB)
        hub.join()

    def add_component(self, component_cls: Type[Component], **kwargs) -> Component:
        """
        Add a new component to the application
        """
        if (hub := self.hubs.get(component_cls.HUB)) is None:
            raise RuntimeError(
                f"Cannot schedule {component_cls.__module__}.{component_cls.__qualname__}:"
                f" missing hub {component_cls.HUB!r}")
        hub.fill_component_kwargs(kwargs)
        component = component_cls(**kwargs)
        hub.add_component(component)
        return component

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
