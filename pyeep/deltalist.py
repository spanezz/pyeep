from __future__ import annotations

from collections import deque
from typing import TypeVar, Generic


class Event:
    """
    Generic event, timed by frame counts
    """
    def __init__(self, *, frame_delay: int = 0):
        self.frame_delay: int = frame_delay


EventType = TypeVar("EventType", bound=Event)


class DeltaList(Generic[EventType]):
    """
    Delta list indexing a queue of events by the delay (in frames) at which
    they are scheduled to happen
    """
    def __init__(self) -> None:
        self.events: deque[EventType] = deque()

    def add_event(self, event: EventType):
        """
        Enqueue an event at its frame_delay position.
        """
        if not self.events:
            self.events.append(event)
            return

        insert_index: int | None = None
        for idx, evt in enumerate(self.events):
            if event.frame_delay < evt.frame_delay:
                evt.frame_delay -= event.frame_delay
                insert_index = idx
                break
            else:
                event.frame_delay -= evt.frame_delay

        match insert_index:
            case None:
                self.events.append(event)
            case 0:
                self.events.appendleft(event)
            case _:
                self.events.insert(idx, event)

    def clock_tick(self, frames: int) -> list[EventType]:
        """
        Advance the delta list clock by the given number of frames.

        Get a list with the events that happen in this clock tick, sorted by
        frame delay from the start of the clock tick.
        """
        res: list[EventType] = []
        while self.events and self.events[0].frame_delay < frames:
            evt = self.events.popleft()
            frames -= evt.frame_delay
            if res:
                evt.frame_delay += res[-1].frame_delay
            res.append(evt)
        if self.events:
            self.events[0].frame_delay -= frames
        return res
