from __future__ import annotations

import argparse
import asyncio
import functools
import threading
import queue
from typing import Callable

from .app import App, Component, Hub, Message, check_hub


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


class AIOHub(Hub):
    HUB = "aio"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.HUB, target=self.run)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.tasks: set[asyncio.Task] = set()
        self.pre_loop_queue: queue.Queue[Callable] = queue.Queue()

    def start(self):
        super().start()
        self.thread.start()

    def join(self):
        super().join()
        self.thread.join()

    def _running_in_hub(self) -> bool:
        return threading.current_thread() == self.thread

    def receive(self, msg: Message):
        if self.loop is None:
            self.pre_loop_queue.put(functools.partial(
                self._hub_thread_receive, msg))
        elif self._running_in_hub():
            self._hub_thread_receive(msg)
        else:
            self.loop.call_soon_threadsafe(self._hub_thread_receive, msg)

    def run(self):
        asyncio.run(self.aio_main())

    async def aio_main(self):
        self.loop = asyncio.get_event_loop()

        try:
            # Execute pending callables in pre_loop_queue
            while True:
                self.pre_loop_queue.get_nowait()()
        except queue.Empty:
            pass

        while self.tasks:
            done, pending = await asyncio.wait(list(self.tasks), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                self.logger.debug("component %r terminated", task.get_name())

        self.loop = None
        self.app.remove_hub(self)

    @check_hub
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
            self.pre_loop_queue.put(functools.partial(
                self._hub_thread_add_component, component))
        elif self._running_in_hub():
            self._hub_thread_add_component(component)
        else:
            self.loop.call_soon_threadsafe(self._hub_thread_add_component, component)

    @check_hub
    def _hub_thread_add_component(self, component):
        super()._hub_thread_add_component(component)
        if self.loop:
            # If we have no loop, then all components in self.components are
            # scheduled to start when the loop starts
            self._start_component(component)


class AIOApp(App):
    def __init__(self, args: argparse.Namespace, **kw):
        super().__init__(args, **kw)
        self.add_hub(AIOHub)
