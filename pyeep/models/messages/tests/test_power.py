import json

from pyeep.models import animation
from pyeep.models.messages.power import IncreasePower, SetPower
from pyeep.test.messages import CommandTestCase


class TestSetPower(CommandTestCase[SetPower]):
    message_cls = SetPower
    sample_animation = animation.PowerPulse(power=1, duration_ns=5)
    samples = {
        "zero": SetPower(dst=(), power=0),
        "value": SetPower(dst=(), power=0.25),
        "animation": SetPower(dst=(), power=sample_animation),
    }

    def test_serialize_animation(self) -> None:
        msg = self.samples["animation"]
        self.assertEqual(
            json.loads(msg.as_json)["power"], self.sample_animation.model_dump()
        )

    def test_members(self) -> None:
        self.assertEqual(self.samples["zero"].power, 0)
        self.assertEqual(self.samples["value"].power, 0.25)
        self.assertEqual(self.samples["animation"].power, self.sample_animation)


class TestIncreasePower(CommandTestCase[IncreasePower]):
    message_cls = IncreasePower
    sample_animation = animation.PowerPulse(power=1, duration_ns=5)
    samples = {
        "zero": IncreasePower(dst=(), power=0),
        "value": IncreasePower(dst=(), power=0.25),
        "animation": IncreasePower(dst=(), power=sample_animation),
    }

    def test_serialize_animation(self) -> None:
        msg = self.samples["animation"]
        self.assertEqual(
            json.loads(msg.as_json)["power"], self.sample_animation.model_dump()
        )

    def test_members(self) -> None:
        self.assertEqual(self.samples["zero"].power, 0)
        self.assertEqual(self.samples["value"].power, 0.25)
        self.assertEqual(self.samples["animation"].power, self.sample_animation)
