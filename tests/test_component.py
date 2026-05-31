import unittest
from typing import override

from pyeep.component.component import Component
from pyeep.models.messages import Message
from pyeep.models.messages.message import GroupMessage


class LogReceived(Component):
    def __init__(self, *, name: str) -> None:
        super().__init__(name=name)
        self.received: str = ""

    @override
    async def receive(self, msg: Message) -> None:
        if isinstance(msg, GroupMessage):
            self.received += str(msg.group)


class TestComponent(unittest.IsolatedAsyncioTestCase):
    def test_routing_key(self) -> None:
        a = Component(name="a")
        ab = Component(name="ab")
        ac = Component(name="ac")
        aba = Component(name="aba")
        aca = Component(name="aca")

        ac.add_component(aca)
        a.add_component(ab)
        a.add_component(ac)
        ab.add_component(aba)

        self.assertEqual(a.routing_key, ("a",))
        self.assertEqual(ab.routing_key, ("a", "ab"))
        self.assertEqual(ac.routing_key, ("a", "ac"))
        self.assertEqual(aba.routing_key, ("a", "ab", "aba"))
        self.assertEqual(aca.routing_key, ("a", "ac", "aca"))

    async def test_send(self) -> None:
        root = LogReceived(name="root")
        a = LogReceived(name="a")
        b = LogReceived(name="b")
        aa = LogReceived(name="a")
        root.add_component(a)
        root.add_component(b)
        a.add_component(aa)

        msg1 = GroupMessage(group=1)
        msg2 = GroupMessage(group=2)
        msg3 = GroupMessage(group=3)
        msg4 = GroupMessage(group=4)

        # This reaches everything except root
        await root.send(msg1)
        # This reaches everything except a
        await a.send(msg2)
        # This reaches everything except b
        await b.send(msg3)
        # This reaches everything except aa
        await aa.send(msg4)

        self.assertEqual(root.received, "234")
        self.assertEqual(a.received, "134")
        self.assertEqual(b.received, "124")
        self.assertEqual(aa.received, "123")
