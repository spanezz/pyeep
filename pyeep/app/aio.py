from __future__ import annotations

import argparse
import asyncio
import functools
import threading
import queue
from typing import TYPE_CHECKING, Callable

from . import App, Hub
from ..component.base import check_hub

if TYPE_CHECKING:
    from ..component.aio import AIOComponent


class AIOHub(Hub):
    HUB = "aio"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.HUB, target=self.run)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.tasks: set[asyncio.Task] = set()
        self.pre_loop_queue: queue.SimpleQueue[Callable] = queue.SimpleQueue()

    def start(self):
        super().start()
        self.thread.start()

    def join(self):
        super().join()
        self.thread.join()

    def _running_in_hub(self) -> bool:
        return threading.current_thread() == self.thread

    def run_in_hub(self, f: Callable, *args, **kwargs):
        if self.loop is None:
            self.pre_loop_queue.put(functools.partial(f, *args, **kwargs))
        elif self._running_in_hub():
            f(*args, **kwargs)
        else:
            self.loop.call_soon_threadsafe(functools.partial(f, *args, **kwargs))

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

        def on_done(task):
            if (exc := task.exception()):
                import traceback
                traceback.print_exception(exc)
            self.remove_component(component)

        task.add_done_callback(on_done)

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
