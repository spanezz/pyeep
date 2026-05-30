import json
import unittest
from typing import Any, cast

from pyeep.models.primitive import load_primitive
from pyeep.models import animation


class AnimationMixin(unittest.TestCase):
    def assertSerializes[A: animation.Animation[Any]](self, value: A) -> A:
        # Serialize to dict
        dict1 = value.model_dump()

        buf = json.dumps(dict1)
        dict2 = json.loads(buf)

        with self.assertNoLogs():
            new = load_primitive(dict2)

        assert isinstance(new, animation.Animation)
        self.assertEqual(new.__class__, value.__class__)
        self.assertEqual(new.py_module, value.py_module)
        self.assertEqual(new.py_class, value.py_class)
        return cast(A, new)


class TestPower(AnimationMixin):
    def test_powerpulse(self) -> None:
        for power, duration in ((-1, 1), (-1.5, 2.5), (12, 10), (0, 42)):
            with self.subTest(power=power, duration=duration):
                m = animation.PowerPulse(power=power, duration=duration)
                self.assertEqual(m.power, power)
                self.assertEqual(m.duration, duration)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.power, m.power)
                self.assertEqual(m1.duration, m.duration)
