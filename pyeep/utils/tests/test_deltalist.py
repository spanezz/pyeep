import unittest
from typing import Any

from pyeep.utils.deltalist import DeltaList, Event


class NamedEvent(Event):
    def __init__(self, name: str, **kw: Any) -> None:
        super().__init__(**kw)
        self.name = name


class TestDeltaList(unittest.TestCase):
    def test_empty(self) -> None:
        dl: DeltaList[NamedEvent] = DeltaList()

        self.assertEqual(dl.clock_tick(100), [])
        self.assertEqual(dl.clock_tick(100), [])
        self.assertEqual(dl.clock_tick(0), [])
        self.assertEqual(dl.clock_tick(100), [])

    def test_insert_start(self) -> None:
        dl: DeltaList[NamedEvent] = DeltaList()

        dl.add_event(NamedEvent("first"))
        dl.add_event(NamedEvent("second"))
        dl.add_event(NamedEvent("third"))

        self.assertEqual(
            [evt.name for evt in dl.events], ["first", "second", "third"]
        )

    def test_add_get(self) -> None:
        dl: DeltaList[NamedEvent] = DeltaList()

        dl.add_event(NamedEvent("second", frame_delay=100))
        dl.add_event(NamedEvent("first", frame_delay=10))
        dl.add_event(NamedEvent("fourth", frame_delay=1000))
        dl.add_event(NamedEvent("zero", frame_delay=0))
        dl.add_event(NamedEvent("third", frame_delay=800))

        self.assertEqual(
            [(evt.name, evt.frame_delay) for evt in dl.events],
            [
                ("zero", 0),
                ("first", 10),
                ("second", 90),
                ("third", 700),
                ("fourth", 200),
            ],
        )

        self.assertEqual(
            [(evt.name, evt.frame_delay) for evt in dl.clock_tick(50)],
            [("zero", 0), ("first", 10)],
        )

        self.assertEqual(
            [(evt.name, evt.frame_delay) for evt in dl.events],
            [("second", 50), ("third", 700), ("fourth", 200)],
        )

        self.assertEqual(
            [(evt.name, evt.frame_delay) for evt in dl.clock_tick(100)],
            [("second", 50)],
        )

        self.assertEqual(
            [(evt.name, evt.frame_delay) for evt in dl.events],
            [("third", 650), ("fourth", 200)],
        )

        self.assertEqual(
            [(evt.name, evt.frame_delay) for evt in dl.clock_tick(1000)],
            [("third", 650), ("fourth", 850)],
        )
