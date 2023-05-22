from __future__ import annotations

import functools
import os
import threading
from collections import defaultdict
from queue import Empty, SimpleQueue
from typing import Callable

from .app import Hub
from .component.base import Component, check_hub
from .messages import Message, Shutdown

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # Noqa


class PygameComponent(Component):
    HUB = "pygame"
    # Code of events that the component listens to
    EVENTS: tuple[int, ...] = ()

    @check_hub
    def pygame_event(self, event: pygame.event.Event):
        pass


class PygameHub(Hub):
    HUB = "pygame"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.HUB, target=self.run)
        self.EVENT_HUB = pygame.event.custom_type()
        self.hub_event_queue: SimpleQueue[Callable] = SimpleQueue()
        self.pygame_initialized = False
        self.event_map: defaultdict[int, set[PygameComponent]] = defaultdict(set)

    def start(self) -> None:
        super().start()
        self.thread.start()

    def join(self) -> None:
        super().join()
        self.thread.join()

    def _notify_hub_event_queue(self):
        """
        Inject a pygame event to notify that there are elements in
        hub_event_queue
        """
        if not self.pygame_initialized:
            return
        # It looks like pygame.event.post is thread safe
        # https://stackoverflow.com/questions/15538287/can-i-add-pygame-events-from-a-second-thread
        pygame.event.post(pygame.event.Event(self.EVENT_HUB))

    def _running_in_hub(self) -> bool:
        return threading.current_thread() == self.thread

    def run_in_hub(self, f: Callable, *args, **kwargs):
        if self._running_in_hub():
            f(*args, **kwargs)
        else:
            self.hub_event_queue.put(functools.partial(f, *args, **kwargs))
            self._notify_hub_event_queue()

    def receive(self, msg: Message):
        if isinstance(msg, Shutdown):
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        super().receive(msg)

    @check_hub
    def _hub_thread_add_component(self, component):
        super()._hub_thread_add_component(component)
        for code in component.EVENTS:
            self.event_map[code].add(component)

    @check_hub
    def _hub_thread_remove_component(self, component):
        for code in component.EVENTS:
            self.event_map[code].drop(component)
        super()._hub_thread_remove_component(component)

    @check_hub
    def _process_hub_queue(self):
        try:
            # Execute pending callables in self.hub_event_queue
            while True:
                self.hub_event_queue.get_nowait()()
        except Empty:
            pass

    def run(self):
        pygame.display.init()
        pygame.joystick.init()
        self.pygame_initialized = True
        self._process_hub_queue()
        while True:
            event = pygame.event.wait()
            match event.type:
                case pygame.QUIT:
                    break
                case self.EVENT_HUB:
                    self._process_hub_queue()
                case _:
                    if (components := self.event_map.get(event.type)):
                        for c in components:
                            c.pygame_event(event)
        self.app.remove_hub(self)
