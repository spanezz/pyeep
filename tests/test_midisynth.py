from __future__ import annotations

import unittest

from pyeep.midisynth import Envelope, EnvelopeShape


class TestEnvelope(unittest.TestCase):
    shape = EnvelopeShape(
        attack_level=1.0, attack_time=0.1,
        decay_time=0.2, sustain_level=0.9, release_time=0.2)

    def test_adsr(self):
        e = Envelope(self.shape, frame_time=0, rate=50, velocity=1.0)
        chunk = e.generate(0, 20)
        self.assertEqual(list(chunk), [
            0.0, 0.25, 0.5, 0.75, 1.0,
            1.0,
            0.9888888888888889,
            0.9777777777777777,
            0.9666666666666667,
            0.9555555555555556,
            0.9444444444444444,
            0.9333333333333333,
            0.9222222222222223,
            0.9111111111111111,
            0.9, 0.9, 0.9, 0.9, 0.9, 0.9])

        e.release(30)
        chunk = e.generate(20, 30)
        self.assertEqual(list(chunk), [
            0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9,
            0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.29999999999999993, 0.19999999999999996, 0.09999999999999998, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        self.assertIsNone(e.generate(50, 10))

    def test_adsr_start_level(self):
        e = Envelope(self.shape, frame_time=0, rate=50, start_level=0.5, velocity=1.0)
        chunk = e.generate(0, 20)
        self.assertEqual(list(chunk), [
            0.5, 0.625, 0.75, 0.875, 1.0,
            1.0,
            0.9888888888888889,
            0.9777777777777777,
            0.9666666666666667,
            0.9555555555555556,
            0.9444444444444444,
            0.9333333333333333,
            0.9222222222222223,
            0.9111111111111111,
            0.9, 0.9, 0.9, 0.9, 0.9, 0.9])

        e.release(30)
        chunk = e.generate(20, 30)
        self.assertEqual(list(chunk), [
            0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9,
            0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.29999999999999993, 0.19999999999999996, 0.09999999999999998, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        self.assertIsNone(e.generate(50, 10))

    def test_adr(self):
        e = Envelope(self.shape, frame_time=0, rate=50, velocity=1.0)
        e.release(10)
        chunk = e.generate(0, 20)
        self.assertEqual(list(chunk), [
            0.0, 0.25, 0.5, 0.75, 1.0,

            1.0, 0.9888888888888889, 0.9777777777777777, 0.9666666666666667,
            0.9555555555555556, 0.9444444444444444,

            0.8395061728395061, 0.7345679012345678, 0.6296296296296297,
            0.5246913580246914, 0.41975308641975306, 0.3148148148148149,
            0.2098765432098766, 0.1049382716049383, 0.0])

        self.assertIsNone(e.generate(20, 10))

    def test_ar(self):
        e = Envelope(self.shape, frame_time=0, rate=50, velocity=1.0)
        e.release(3)
        chunk = e.generate(0, 15)
        self.assertEqual(list(chunk), [
            0.0, 0.25, 0.5, 0.75,
            0.6666666666666666, 0.5833333333333334, 0.5, 0.4166666666666667,
            0.33333333333333337, 0.25, 0.16666666666666674,
            0.08333333333333337, 0.0, 0.0, 0.0])

        self.assertIsNone(e.generate(15, 10))
