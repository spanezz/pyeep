import unittest

from pyeep.models.color import Color


class TestColor(unittest.TestCase):
    def test_deserialize(self) -> None:
        for val in (
            "#ff0000",
            {"red": 1, "green": 0.0, "blue": 0},
            Color(red=1, green=0, blue=0),
        ):
            with self.subTest(val=repr(val)):
                self.assertEqual(
                    Color.model_validate(val), Color(red=1, green=0, blue=0)
                )
