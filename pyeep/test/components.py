from typing import Unpack, override

from pyeep.models.messages import (
    Broadcast,
    Command,
    Event,
    Message,
)
from pyeep.nodes import Component, ComponentArgs, Hub, HubArgs


class ConcreteHub(Hub):
    """
    Concrete version of Hub to use for testing.

    By default, all outbound messages are stored in lists.
    """

    def __init__(self, **kwargs: Unpack[HubArgs]) -> None:
        super().__init__(**kwargs)
        self.sent_events: list[Event] = []
        self.sent_broadcasts: list[Broadcast] = []
        self.sent_commands: list[Command] = []

    @override
    async def outbound_event(self, msg: Event) -> None:
        self.sent_events.append(msg)

    @override
    async def outbound_broadcast(self, msg: Broadcast) -> None:
        self.sent_broadcasts.append(msg)

    @override
    async def outbound_command(self, msg: Command) -> None:
        self.sent_commands.append(msg)


class ConcreteComponent(Component):
    """
    Concrete version of Component to use for testing.

    By default, all received messages are stored in a list.
    """

    def __init__(self, **kwargs: Unpack[ComponentArgs]) -> None:
        super().__init__(**kwargs)
        self.received: list[Message] = []

    @override
    async def receive(self, msg: Message) -> None:
        self.received.append(msg)
