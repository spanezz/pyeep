from __future__ import annotations

import argparse
import asyncio

from .app import App, Component, ThreadHub, Message


class AIOComponent(Component):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_queue: asyncio.Queue[Message] = asyncio.Queue()

    def shutdown(self):
        super().shutdown()

    def receive(self, msg: Message):
        self.message_queue.put_nowait(msg)

    async def next_message(self, *, timeout: float | None = None) -> Message | None:
        try:
            return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def run(self):
        pass


class AIOThread(ThreadHub):
    def __init__(self):
        super().__init__(name="aio")
        self.loop: asyncio.AbstractEventLoop | None = None

    def receive(self, msg: Message):
        if self.loop is None:
            return
        self.loop.call_soon_threadsafe(super().receive, msg)

    def shutdown(self):
        if self.loop is None:
            return
        self.loop.call_soon_threadsafe(super().shutdown)

    def run(self):
        asyncio.run(self.aio_main())

    async def aio_main(self):
        self.loop = asyncio.get_event_loop()
        await asyncio.gather(
            *(c.run() for c in self.components.values())
        )

    def add_component(self, component: Component) -> bool:
        if isinstance(component, AIOComponent):
            self.components[component.name] = component
            component.hub = self
            return True

        return super().add_component(component)


class AIOApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_hub(AIOThread())
