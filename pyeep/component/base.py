from __future__ import annotations

import functools
import logging
import time
from typing import TYPE_CHECKING, Any, Type

if TYPE_CHECKING:
    from ..messages.message import Message
    from .controller import Controller
    from ..app import Hub


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
    HUB: str

    def __init__(self, *, hub: "Hub", name: str | None = None):
        self.name = name if name is not None else self.__class__.__name__.lower()
        self.logger = logging.getLogger(self.name)
        self.hub = hub

    def __str__(self) -> str:
        return self.name

    @check_hub
    def load_config(self, config: dict[str, Any]):
        """
        Load configuration from a dict.

        This is called just after component initialization, if config exists
        """
        pass

    @property
    def description(self) -> str:
        return self.name

    def get_controller(self) -> Type["Controller"]:
        raise NotImplementedError(f"{self.__class__.__name__}.get_controller not implemented")

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

    @check_hub
    def get_config(self) -> dict[str, Any]:
        """
        Return the configuration for this component as a dict
        """
        return {}
