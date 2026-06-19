import json
import unittest
from typing import Any, cast, override

from pyeep.models import animation
from pyeep.models.primitive import load_primitive


class AnimationMixin(unittest.TestCase):
    def assertSerializes[A: animation.AnimationPrimitive[Any]](
        self, value: A
    ) -> A:
        # Serialize to dict
        dict1 = value.model_dump()

        buf = json.dumps(dict1)
        dict2 = json.loads(buf)

        with self.assertNoLogs():
            new = load_primitive(dict2)

        assert isinstance(new, animation.AnimationPrimitive)
        self.assertEqual(new.__class__, value.__class__)
        self.assertEqual(new.primitive, value.primitive)
        return cast(A, new)


class TestAnimations(unittest.TestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.animations = animation.PowerAnimations()
        self.last_checked_time_ns: int = -1

    def add(
        self, start_time_ns: int, a: animation.AnimationPrimitive[float]
    ) -> animation.Animation[float]:
        self.animations.add(start_time_ns, res := a.get_animation())
        return res

    def assert_active_animations(
        self, *animations: animation.Animation[float]
    ) -> None:
        self.assertEqual(
            {x[1] for x in self.animations.animations}, set(animations)
        )

    def assert_value(self, time_ns: int, value: float | None) -> None:
        if time_ns <= self.last_checked_time_ns:
            self.fail(
                f"{time_ns} checked after {self.last_checked_time_ns},"
                " but they should be always increasing"
            )
        self.last_checked_time_ns = time_ns
        self.assertEqual(self.animations.value(time_ns), value)

    def test_one(self) -> None:
        self.add(10, animation.Const(value=1, duration_ns=20))
        self.assertEqual(self.animations.value(0), 0)
        self.assertEqual(self.animations.value(9), 0)
        self.assertEqual(self.animations.value(10), 1)
        self.assertEqual(self.animations.value(20), 1)
        self.assertEqual(self.animations.value(29), 1)
        self.assertEqual(self.animations.value(30), 0)
        self.assertEqual(self.animations.value(40), None)

    def test_overlaps(self) -> None:
        # From 10 to 30
        a10 = self.add(10, animation.Const(value=1, duration_ns=20))
        # From 15 to 40
        a15 = self.add(15, animation.Const(value=10, duration_ns=25))
        # From 5 to 55
        a5 = self.add(5, animation.Const(value=100, duration_ns=50))
        # From 16 to 20
        a16 = self.add(16, animation.Const(value=1000, duration_ns=4))
        # From 18 to 20
        a18 = self.add(18, animation.Const(value=10000, duration_ns=2))

        self.assert_value(0, 0)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(4, 0)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(5, 100)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(9, 100)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(10, 101)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(14, 101)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(15, 111)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(16, 1111)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(17, 1111)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(18, 11111)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(19, 11111)
        self.assert_active_animations(a10, a15, a5, a16, a18)

        self.assert_value(20, 111)
        self.assert_active_animations(a10, a15, a5)

        self.assert_value(21, 111)
        self.assert_active_animations(a10, a15, a5)

        self.assert_value(29, 111)
        self.assert_active_animations(a10, a15, a5)

        self.assert_value(30, 110)
        self.assert_active_animations(a15, a5)

        self.assert_value(39, 110)
        self.assert_active_animations(a15, a5)

        self.assert_value(40, 100)
        self.assert_active_animations(a5)

        self.assert_value(54, 100)
        self.assert_active_animations(a5)

        self.assert_value(55, 0)
        self.assert_active_animations()

        self.assert_value(100, None)
        self.assert_active_animations()


class TestPower(AnimationMixin):
    def test_powerpulse(self) -> None:
        for power, duration in ((-1, 1), (-1.5, 25), (12, 10), (0, 42)):
            with self.subTest(power=power, duration=duration):
                m = animation.PowerPulse(power=power, duration_ns=duration)
                self.assertEqual(m.power, power)
                self.assertEqual(m.duration_ns, duration)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.power, m.power)
                self.assertEqual(m1.duration_ns, m.duration_ns)
