import json

from pyeep.models import animation
from pyeep.models.color import Color
from pyeep.models.messages.color import SetColor
from pyeep.test.messages import CommandTestCase


class TestSetColor(CommandTestCase[SetColor]):
    message_cls = SetColor

    sample_color = Color(red=1, green=0.5, blue=0.1)
    sample_animation = animation.ColorHeartPulse(
        color=Color(red=0.5, green=0, blue=0),
        duration_ns=100_000_000,
        atrial_duration_ratio=0.3,
    )
    samples = {
        "value": SetColor(dst=(), color=sample_color),
        "animation": SetColor(dst=(), color=sample_animation),
    }

    def test_serialize_animation(self) -> None:
        msg = self.samples["animation"]
        self.assertEqual(
            json.loads(msg.as_json)["color"],
            {
                "primitive": "pyeep.models.animation.ColorHeartPulse",
                "atrial_duration_ratio": 0.3,
                "color": {"blue": 0.0, "green": 0.0, "red": 0.5},
                "duration_ns": 100000000,
            },
        )

    def test_members(self) -> None:
        self.assertEqual(self.samples["value"].color, self.sample_color)
        self.assertEqual(self.samples["animation"].color, self.sample_animation)
