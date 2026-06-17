import unittest

from pyeep.models.messages import build_routing_keys
from pyeep.models.messages.power import SetPower
from pyeep.nodes.messages import NewComponent, Shutdown
from pyeep.test.components import ConcreteHub, ConcreteComponent


class TestComponent(unittest.IsolatedAsyncioTestCase):
    def test_routing_key(self) -> None:
        hub = ConcreteHub(name="hub")
        a = ConcreteComponent(name="a", hub=hub)
        self.assertEqual(a.routing_key, "hub.a")

    async def test_send(self) -> None:
        hub = ConcreteHub(name="hub")
        a = ConcreteComponent(name="a", hub=hub)

        await a.send_event(evt := NewComponent())
        await a.send_broadcast(brd := Shutdown())
        await a.send_command(
            cmd := SetPower(power=1, dst=build_routing_keys(["testnode"]))
        )

        self.assertEqual(
            hub.sent_events, [evt.model_copy(update={"src": a.routing_key})]
        )
        self.assertEqual(
            hub.sent_broadcasts, [brd.model_copy(update={"src": a.routing_key})]
        )
        self.assertEqual(
            hub.sent_commands, [cmd.model_copy(update={"src": a.routing_key})]
        )
