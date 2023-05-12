from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import TYPE_CHECKING, Iterator, NamedTuple

if TYPE_CHECKING:
    from .hub import Hub
    from ..messages import Message


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


def export(f):
    """
    Decorator that makes a component function callable from any hub context
    """
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs) -> None:
        self.hub.run_in_hub(f, self, *args, **kwargs)
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
        if msg.ts is None:
            msg.ts = time.time()
        if self.hub is not None:
            self.hub.send(msg)

    @check_hub
    def receive(self, msg: "Message"):
        """
        Function called by the hub to deliver a message to this component
        """
        pass


class ModeInfo(NamedTuple):
    """
    Information about one input mode
    """
    name: str
    summary: str


class ModeMixin(Component):
    """
    Mixin for components to implement multiple operational modes
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_mode("default")

    def list_modes(self) -> Iterator[ModeInfo, None]:
        """
        List available modes
        """
        for name, value in inspect.getmembers(self, inspect.ismethod):
            if not name.startswith("mode_"):
                continue
            yield ModeInfo(name[5:], inspect.getdoc(value))

    @export
    def set_mode(self, name: str) -> None:
        """
        Set the active mode
        """
        self.mode = getattr(self, "mode_" + name)
