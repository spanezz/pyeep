from __future__ import annotations

import unittest

from pyeep.deltalist import Event, DeltaList


class TestEvent(Event):
    def __init__(self, name: str, **kw):
        super().__init__(**kw)
        self.name = name


class TestDeltaList(unittest.TestCase):
    def test_empty(self):
        dl = DeltaList()

        self.assertEqual(dl.clock_tick(100), [])
        self.assertEqual(dl.clock_tick(100), [])
        self.assertEqual(dl.clock_tick(0), [])
        self.assertEqual(dl.clock_tick(100), [])

    def test_insert_start(self):
        dl = DeltaList()

        dl.add_event(TestEvent("first"))
        dl.add_event(TestEvent("second"))
        dl.add_event(TestEvent("third"))

        self.assertEqual([evt.name for evt in dl.events], ["first", "second", "third"])

    def test_add_get(self):
        dl = DeltaList()

        dl.add_event(TestEvent("second", frame_delay=100))
        dl.add_event(TestEvent("first", frame_delay=10))
        dl.add_event(TestEvent("fourth", frame_delay=1000))
        dl.add_event(TestEvent("zero", frame_delay=0))
        dl.add_event(TestEvent("third", frame_delay=800))

        self.assertEqual(
                [(evt.name, evt.frame_delay) for evt in dl.events],
                [("zero", 0),
                 ("first", 10),
                 ("second", 90),
                 ("third", 700),
                 ("fourth", 200)])

        self.assertEqual(
                [(evt.name, evt.frame_delay) for evt in dl.clock_tick(50)],
                [("zero", 0),
                 ("first", 10)])

        self.assertEqual(
                [(evt.name, evt.frame_delay) for evt in dl.events],
                [("second", 50),
                 ("third", 700),
                 ("fourth", 200)])

        self.assertEqual(
                [(evt.name, evt.frame_delay) for evt in dl.clock_tick(100)],
                [("second", 50)])

        self.assertEqual(
                [(evt.name, evt.frame_delay) for evt in dl.events],
                [("third", 650),
                 ("fourth", 200)])

        self.assertEqual(
                [(evt.name, evt.frame_delay) for evt in dl.clock_tick(1000)],
                [("third", 650),
                 ("fourth", 850)])
