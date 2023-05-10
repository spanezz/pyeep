from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING

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
        if self.hub is not None:
            self.hub.send(msg)

    @check_hub
    def receive(self, msg: "Message"):
        """
        Function called by the hub to deliver a message to this component
        """
        pass
