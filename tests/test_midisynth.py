from __future__ import annotations

import unittest

import mido
import numpy

from pyeep.midisynth import OnOff


class TestOnOff(unittest.TestCase):
    def test_empty(self):
        note = OnOff(0, numpy.float32)
        self.assertIsNone(note.generate(0, 100))
        self.assertIsNone(note.generate(1000, 2048))

    def test_note_on(self):
        note = OnOff(0, numpy.float32)
        note.add_event(mido.Message("note_on", velocity=64, time=1024))

        a = note.generate(0, 512)
        self.assertEqual(len(a), 512)
        self.assertEqual(sum(a), 0)

        a = note.generate(1000, 1000)
        self.assertEqual(len(a), 1000)
        self.assertEqual(list(a[:24]), [0.0] * 24)
        self.assertEqual(list(a[24:]), [64/127] * 976)

        a = note.generate(2000, 1000)
        self.assertEqual(len(a), 1000)
        self.assertEqual(list(a), list(numpy.full(1000, 64/127, dtype=numpy.float32)))

    def test_note_on_off(self):
        note = OnOff(0, numpy.float32)
        note.add_event(mido.Message("note_on", velocity=64, time=3))
        note.add_event(mido.Message("note_off", time=6))

        a = [int(x * 1000) for x in note.generate(0, 10)]
        val = int(64/127 * 1000)
        self.assertEqual(list(a), [0, 0, 0, val, val, val, 0, 0, 0, 0])

        self.assertIsNone(note.generate(10, 15))
