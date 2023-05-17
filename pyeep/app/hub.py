from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from .component import check_hub

if TYPE_CHECKING:
    from .app import App
    from .component import Component
    from ..messages import Message


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

    def run_in_hub(self, f: Callable, *args, **kw):
        """
        Call the function with the given arguments in the hub context as soon
        as it's possible
        """
        raise NotImplementedError(f"{self.__class__.__name__}.run_in_hub")

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
        self.run_in_hub(self._hub_thread_receive, msg)

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
        elif (comp := self.components.get(msg.dst)) is not None:
            comp.receive(msg)

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
        self.run_in_hub(self._hub_thread_add_component, component)

    @check_hub
    def _hub_thread_add_component(self, component):
        self.components[component.name] = component
        self.logger.debug("new component %r", component.name)

    def remove_component(self, component: Component):
        """
        Remove the component from this hub
        """
        self.run_in_hub(self._hub_thread_remove_component, component)

    @check_hub
    def _hub_thread_remove_component(self, component):
        component.cleanup()
        del self.components[component.name]
        self.logger.debug("removed component %r", component.name)
