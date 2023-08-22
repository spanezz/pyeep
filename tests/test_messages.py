from __future__ import annotations

import json
import unittest
from unittest import mock

from pyeep.messages.component import (ComponentActiveStateChanged,
                                      DeviceScanRequest, NewComponent,
                                      Shutdown)
from pyeep.messages.jsonable import Jsonable
from pyeep.messages.message import Message


class MessageMixin:
    def assertSerializes(self, msg: Message) -> Message:
        # Serialize to dict
        dict1 = msg.as_jsonable()

        buf = json.dumps(dict1)
        dict2 = json.loads(buf)

        cls = Jsonable.jsonable_class(dict2)
        self.assertEqual(cls, msg.__class__)

        msg1 = cls(**dict2)
        self.assertEqual(msg1.ts, msg.ts)

        return msg1


class TestMessage(MessageMixin, unittest.TestCase):
    def test_message(self):
        m = Message()
        self.assertEqual(m.name, "message")
        self.assertIsInstance(m.ts, float)
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)

        m1 = self.assertSerializes(m)
        self.assertEqual(m1.name, "message")
        self.assertIsNone(m1.src)
        self.assertIsNone(m1.dst)


class TestComponent(MessageMixin, unittest.TestCase):
    def test_shutdown(self):
        m = Shutdown()
        self.assertEqual(m.name, "shutdown")
        self.assertIsInstance(m.ts, float)
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)

        m1 = self.assertSerializes(m)
        self.assertEqual(m1.name, "shutdown")
        self.assertIsNone(m1.src)
        self.assertIsNone(m1.dst)

    def test_newcomponent(self):
        m = NewComponent()
        self.assertEqual(m.name, "newcomponent")
        self.assertIsInstance(m.ts, float)
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)

        m1 = self.assertSerializes(m)
        self.assertEqual(m1.name, "newcomponent")
        self.assertIsNone(m1.src)
        self.assertIsNone(m1.dst)

    def test_componentactivestatechanged(self):
        m = ComponentActiveStateChanged(value=True)
        self.assertEqual(m.name, "componentactivestatechanged")
        self.assertIsInstance(m.ts, float)
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)
        self.assertTrue(m.value)

        m1 = self.assertSerializes(m)
        self.assertEqual(m1.name, "componentactivestatechanged")
        self.assertIsNone(m1.src)
        self.assertIsNone(m1.dst)
        self.assertTrue(m1.value)

    def test_devicescanrequest(self):
        m = DeviceScanRequest(duration=3.14)
        self.assertEqual(m.name, "devicescanrequest")
        self.assertIsInstance(m.ts, float)
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)
        self.assertEqual(m.duration, 3.14)

        m1 = self.assertSerializes(m)
        self.assertEqual(m1.name, "devicescanrequest")
        self.assertIsNone(m1.src)
        self.assertIsNone(m1.dst)
        self.assertEqual(m1.duration, 3.14)
