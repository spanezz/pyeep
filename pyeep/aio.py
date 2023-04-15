from __future__ import annotations

import argparse
import asyncio
import threading

from .app import App, Component, Hub, Message


class AIOComponent(Component):
    """
    Component running on an asyncio event loop
    """
    HUB = "aio"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_queue: asyncio.Queue[Message] = asyncio.Queue()

    def receive(self, msg: Message):
        self.message_queue.put_nowait(msg)

    async def next_message(self, *, timeout: float | None = None) -> Message | None:
        """
        Wait for reception of a message, with an optional timeout
        """
        try:
            return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def run(self):
        """
        Main body of this component
        """
        pass


class AIOThread(Hub):
    HUB = "aio"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.HUB, target=self.run)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.tasks: set[asyncio.Task] = set()

    def start(self):
        super().start()
        self.thread.start()

    def join(self):
        super().join()
        self.thread.join()

    def receive(self, msg: Message):
        if self.loop is None:
            return
        self.loop.call_soon_threadsafe(self._hub_thread_receive, msg)

    def run(self):
        asyncio.run(self.aio_main())

    async def aio_main(self):
        self.loop = asyncio.get_event_loop()
        for c in self.components.values():
            self._start_component(c)

        while self.tasks:
            done, pending = await asyncio.wait(list(self.tasks), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                self.logger.debug("component %r terminated", task.get_name())

        self.loop = None
        self.app.remove_hub(self)

    def _start_component(self, component: AIOComponent):
        """
        Start a task for this component.

        This function needs to be called in the aio thread, with a running loop
        """
        task = asyncio.create_task(component.run(), name=component.name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def add_component(self, component: Component):
        if self.loop is None:
            self._hub_thread_add_component(component)
        else:
            self.loop.call_soon_threadsafe(self._hub_thread_add_component, component)

    def _hub_thread_add_component(self, component):
        super()._hub_thread_add_component(component)
        if self.loop:
            # If we have no loop, then all components in self.components are
            # scheduled to start when the loop starts
            self._start_component(component)


class AIOApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_hub(AIOThread)
