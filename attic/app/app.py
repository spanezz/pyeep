import argparse
import functools
import logging
import sys
import threading
from collections.abc import Callable
from queue import SimpleQueue
from typing import IO, TypeVar

from pyeep.nodes.component import Component
from pyeep.app.base import BaseApp
from pyeep.app.hub import Hub
from pyeep.models.messages.component import NewComponent, Shutdown
from pyeep.models.messages.message import Message

try:
    import coloredlogs

    HAVE_COLOREDLOGS = True
except ModuleNotFoundError:
    HAVE_COLOREDLOGS = False


log = logging.getLogger(__name__)

C = TypeVar("C", bound=Component)


class App(BaseApp):
    """
    Base application class
    """

    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__()
        self.args = args
        self.hubs: dict[str, Hub] = {}
        self.hubs_lock = threading.Lock()
        self.command_queue: SimpleQueue[Callable] = SimpleQueue()

    def add_hub(self, hub_cls: type[Hub], **kwargs):
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
        self.command_queue.put(
            functools.partial(self._app_thread_remove_hub, hub)
        )

    def _app_thread_remove_hub(self, hub: Hub):
        """
        Remove a hub from teh application.

        This function is called from the App's thread.
        """
        log.debug("%s: hub shutting down", hub.HUB)
        with self.hubs_lock:
            self.hubs.pop(hub.HUB)
        hub.join()

    def add_component(self, component_cls: type[C], **kwargs) -> C:
        """
        Add a new component to the application
        """
        if (hub := self.hubs.get(component_cls.HUB)) is None:
            raise RuntimeError(
                f"Cannot schedule {component_cls.__module__}.{component_cls.__qualname__}:"
                f" missing hub {component_cls.HUB!r}"
            )
        hub.fill_component_kwargs(kwargs)
        component = component_cls(**kwargs)
        hub.add_component(component)

        msg = NewComponent(src=str(component))
        self.send(msg)

        return component

    def get_component(self, name: str) -> Component:
        """
        Lookup a component by name.

        Raise KeyError if the component was not found in any hub
        """
        for hub in self.hubs.values():
            if (c := hub.components.get(name)) is not None:
                return c
        raise KeyError(name)

    def send(self, msg: Message):
        """
        Send a message to the applcation components
        """
        self.command_queue.put(functools.partial(self._app_thread_send, msg))

    def _app_thread_send(self, msg: Message):
        """
        Dispatch the message.

        This function is called from the App's thread
        """
        log.debug(
            "Message: %s → %s: %s",
            msg.src,
            msg.dst,
            msg,
        )
        for hub in self.hubs.values():
            hub.receive(msg)

    def main_init(self):
        """
        Initialize the application before entering the main loop
        """
        self.setup_logging()
        for hub in self.hubs.values():
            hub.start()

    def _next_command(self) -> Callable:
        """
        Mockable wrapper around self.command_queue.get()
        """
        return self.command_queue.get()

    def main_loop(self):
        """
        Main loop. The application will shut down after this function returns
        """
        while self.hubs:
            try:
                c = self._next_command()
            except KeyboardInterrupt:
                log.info(
                    "Keyboard interrupt received: shutting down application"
                )
                self.send(Shutdown())
            else:
                c()

    def main_shutdown(self):
        """
        Shut down the application
        """

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
            print(
                f"{hname} ({hub.__class__.__module__}.{hub.__class__.__name__})",
                file=file,
            )
            for cname, comp in hub.components.items():
                print(
                    f" - {cname} ({comp.__class__.__module__}.{comp.__class__.__name__})",
                    file=file,
                )
