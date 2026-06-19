import json
from unittest import TestCase

from pyeep.models import load_primitive
from pyeep.models.messages import Broadcast, Command, Event, Message


class MessageTestCase[M: Message](TestCase):
    #: Message class to test
    message_cls: type[M]
    #: Sample messages to test
    samples: dict[str, M] = {}

    def assertSerializes(self, msg: M) -> M:
        # Serialize to dict
        dict1 = msg.model_dump()

        buf = json.dumps(dict1)
        self.assertEqual(buf, msg.as_json)
        dict2 = json.loads(buf)

        with self.assertNoLogs():
            newmsg = load_primitive(dict2)

        assert isinstance(newmsg, self.message_cls)
        self.assertEqual(newmsg.__class__, msg.__class__)
        self.assertEqual(newmsg, msg)
        return newmsg

    def test_serialization(self) -> None:
        for name, msg in self.samples.items():
            with self.subTest(name=name):
                self.assertSerializes(msg)


class EventTestCase[M: Event](MessageTestCase[M]):
    pass


class BroadcastTestCase[M: Broadcast](MessageTestCase[M]):
    pass


class CommandTestCase[M: Command](MessageTestCase[M]):
    pass
