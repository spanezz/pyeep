import json
import unittest
from typing import cast

from pyeep.models.primitive import Primitive, load_primitive
from pyeep.models.messages.message import Message, GroupMessage
from pyeep.models.messages.component import (
    ComponentActiveStateChanged,
    DeviceScanRequest,
    NewComponent,
    Shutdown,
)
from pyeep.models.messages.config import ConfigSaveRequest, Configure
from pyeep.models.messages.input import EmergencyStop, Pause, Resume, Shortcut
from pyeep.models.messages import power
from pyeep.models import animation


class MessageMixin(unittest.TestCase):
    def assertSerializes[M: Message](self, msg: M) -> M:
        # Serialize to dict
        dict1 = msg.model_dump()

        buf = json.dumps(dict1)
        dict2 = json.loads(buf)

        with self.assertNoLogs():
            newmsg = load_primitive(dict2)

        assert isinstance(newmsg, Message)
        self.assertEqual(newmsg.__class__, msg.__class__)
        self.assertEqual(newmsg.py_module, msg.py_module)
        self.assertEqual(newmsg.py_class, msg.py_class)
        self.assertEqual(newmsg.name, msg.name)
        self.assertEqual(newmsg.ts, msg.ts)
        self.assertEqual(newmsg.src, msg.src)
        self.assertEqual(newmsg.dst, msg.dst)
        return cast(M, newmsg)


class TestBase(MessageMixin, unittest.TestCase):
    def test_message(self) -> None:
        m = Message()
        self.assertEqual(m.py_module, "pyeep.models.messages.message")
        self.assertEqual(m.py_class, "Message")
        self.assertEqual(m.name, "message")
        self.assertIsInstance(m.ts, int)
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)

        self.assertSerializes(m)

    def test_groupmessage(self) -> None:
        for group in -1, 0, 42:
            with self.subTest(group=group):
                m = GroupMessage(group=group)
                self.assertEqual(m.name, "groupmessage")
                self.assertIsNone(m.src)
                self.assertIsNone(m.dst)
                self.assertEqual(m.group, group)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.group, m.group)


class TestComponent(MessageMixin, unittest.TestCase):
    def test_shutdown(self) -> None:
        m = Shutdown()
        self.assertEqual(m.name, "shutdown")
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)

        self.assertSerializes(m)

    def test_newcomponent(self) -> None:
        m = NewComponent()
        self.assertEqual(m.name, "newcomponent")
        self.assertIsNone(m.src)
        self.assertIsNone(m.dst)

        self.assertSerializes(m)

    def test_componentactivestatechanged(self) -> None:
        for value in True, False:
            with self.subTest(value=value):
                m = ComponentActiveStateChanged(value=value)
                self.assertEqual(m.name, "componentactivestatechanged")
                self.assertEqual(m.value, value)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.value, m.value)

    def test_devicescanrequest(self) -> None:
        for duration in 1, 3.14:
            with self.subTest(duration=duration):
                m = DeviceScanRequest(duration=duration)
                self.assertEqual(m.name, "devicescanrequest")
                self.assertEqual(m.duration, duration)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.duration, m.duration)


class TestConfig(MessageMixin, unittest.TestCase):
    def test_configsaverequest(self) -> None:
        m = ConfigSaveRequest()
        self.assertEqual(m.name, "configsaverequest")

        self.assertSerializes(m)

    def test_configure(self) -> None:
        for value in ({"test": "val"}, {"foo": 42}, {"foo": True, "bar": None}):
            with self.subTest(value=value):
                m = Configure(config=value)
                self.assertEqual(m.name, "configure")
                self.assertEqual(m.config, value)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.config, value)


class TestInput(MessageMixin, unittest.TestCase):
    def test_emergencystop(self) -> None:
        m = EmergencyStop()
        self.assertEqual(m.name, "emergencystop")

        self.assertSerializes(m)

    def test_shortcut(self) -> None:
        for command in ("test", "test2"):
            with self.subTest(command=command):
                m = Shortcut(command=command)
                self.assertEqual(m.name, "shortcut")
                self.assertEqual(m.command, command)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.command, m.command)

    def test_pause(self) -> None:
        m = Pause(group=3)
        self.assertEqual(m.name, "pause")

        self.assertSerializes(m)

    def test_resume(self) -> None:
        m = Resume(group=3)
        self.assertEqual(m.name, "resume")

        self.assertSerializes(m)


class TestPower(MessageMixin, unittest.TestCase):
    def test_setrate(self) -> None:
        for rate in (0, 3.14, 42):
            with self.subTest(rate=rate):
                m = power.SetRate(rate=rate)
                self.assertEqual(m.name, "setrate")
                self.assertEqual(m.rate, rate)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.rate, rate)

    def test_setpower(self) -> None:
        for value in (0, 3.14, 42):
            with self.subTest(power=power):
                m = power.SetPower(power=value)
                self.assertEqual(m.name, "setpower")
                self.assertEqual(m.power, value)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.power, m.power)

    def test_setgrouppower(self) -> None:
        for value in (0, 3.14, 42, animation.PowerPulse(power=1, duration=0.5)):
            with self.subTest(value=value):
                m = power.SetGroupPower(group=2, power=value)
                self.assertEqual(m.name, "setgrouppower")
                self.assertEqual(m.power, value)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.power, m.power)

    def test_increasegrouppower(self) -> None:
        for value in (0, 3.14, 42, animation.PowerPulse(power=1, duration=0.5)):
            with self.subTest(value=value):
                m = power.IncreaseGroupPower(group=2, amount=value)
                self.assertEqual(m.name, "increasegrouppower")
                self.assertEqual(m.amount, value)

                m1 = self.assertSerializes(m)
                self.assertEqual(m1.amount, m.amount)
