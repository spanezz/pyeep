import abc
from functools import cached_property
import logging
from typing import override

from pyeep.models.messages import Message


class BaseComponent(abc.ABC):
    """A pyeep component that can send and receive messages."""

    def __init__(self, *, name: str) -> None:
        self.name = name
        self.log = logging.getLogger(self.get_logger_name())

    @override
    def __str__(self) -> str:
        return self.name

    def get_logger_name(self) -> str:
        """Return the name to use for logging."""
        return self.name

    @abc.abstractmethod
    async def send(self, msg: Message) -> None:
        """Send a message to other components."""

    async def receive(self, msg: Message) -> None:
        """Deliver a message to this component."""
        # Do nothing by default


#    @check_hub
#    def load_config(self, config: dict[str, Any]):
#        """
#        Load configuration from a dict.
#
#        This is called just after component initialization, if config exists
#        """
#
#    @property
#    def description(self) -> str:
#        return self.name
#
#    def get_controller(self) -> type["Controller"]:
#        raise NotImplementedError(
#            f"{self.__class__.__name__}.get_controller not implemented"
#        )
#
#    @check_hub
#    def cleanup(self):
#        """
#        Cleanup/release resources before this component is removed
#        """
#
#    @check_hub
#    def get_config(self) -> dict[str, Any]:
#        """
#        Return the configuration for this component as a dict
#        """
#        return {}


class Component(BaseComponent):
    """Component with message routing."""

    def __init__(self, *, name: str) -> None:
        super().__init__(name=name)
        self.upstream: Component | None = None
        self.downstream: dict[str, Component] = {}

    @cached_property
    def routing_key(self) -> tuple[str, ...]:
        """
        Return the routing key for this component.

        The result is cached, so calling this before the component has been set
        up in the component hierarchy will cache a wrong value.
        """
        if not self.upstream:
            return (self.name,)
        else:
            return self.upstream.routing_key + (self.name,)

    def set_upstream(self, component: "Component") -> None:
        """Set the upstream component."""
        self.upstream = component

    def add_component(self, component: "Component") -> None:
        if component.name in self.downstream:
            raise ValueError(
                f"Component {component.name} already present in {self.name}"
            )
        component.set_upstream(self)
        self.downstream[component.name] = component

    def _match_downstream(self, msg: Message) -> str | None:
        """
        Get the downstream component name, if applicable.

        If the ``msg.src`` begins with our routing key, return the next
        component name, else return None.

        This can be used to check if the message comes from a subcomponent of
        this component.
        """
        if msg.src is None:
            return None
        rk = self.routing_key
        if msg.src[: len(rk)] != rk or len(msg.src) <= len(rk):
            return None
        return msg.src[len(rk)]

    async def route_up(self, msg: Message) -> None:
        """Route this message to the upstream component."""
        if self.upstream:
            await self.upstream.route(msg)

    async def route(self, msg: Message) -> None:
        """Route this message to upstream and downstream components."""
        if msg.src is None:
            raise ValueError(
                "Cannot route a message that did not pass through send()"
            )
        rk = self.routing_key

        if msg.src[: len(rk)] == rk:
            # If our rk is same or a prefix of the message rk, send up
            await self.route_up(msg)

            # If our rk is a strict prefix of the message rk, send down except
            # when rk is also a prefix of downstream
            for component in self.downstream.values():
                crk = component.routing_key
                if msg.src[: len(crk)] != crk:
                    await component.route(msg)
        else:
            # If our rk is not a prefix of the message rk, send down
            for component in self.downstream.values():
                await component.route(msg)

        if msg.src != rk:
            # If the message is not from us, deliver it
            await self.receive(msg)

    @override
    async def send(self, msg: Message) -> None:
        """Send message to the upstream router."""
        if msg.src is not None:
            raise ValueError(
                "trying to send a message with an existing sender key"
            )
        msg = msg.model_copy(update={"src": self.routing_key})
        await self.route(msg)
