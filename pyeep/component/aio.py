from __future__ import annotations

import asyncio

from ..messages import Message
from .base import Component, check_hub


class AIOComponent(Component):
    """
    Component running on an asyncio event loop
    """
    HUB = "aio"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.message_queue: asyncio.Queue[Message] = asyncio.Queue()

    @check_hub
    def receive(self, msg: Message):
        self.message_queue.put_nowait(msg)

    @check_hub
    async def next_message(self, *, timeout: float | None = None) -> Message | None:
        """
        Wait for reception of a message, with an optional timeout
        """
        try:
            return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def run(self) -> None:
        """
        Main body of this component
        """
        pass
