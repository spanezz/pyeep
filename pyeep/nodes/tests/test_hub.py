import unittest

from pyeep.models.messages import build_routing_keys
from pyeep.models.messages.power import SetPower
from pyeep.nodes.messages import NewComponent, Shutdown
from pyeep.test.components import ConcreteHub, ConcreteComponent


class TestHub(unittest.IsolatedAsyncioTestCase):
    def test_routing_key(self) -> None:
        hub = ConcreteHub(name="hub")
        self.assertEqual(hub.routing_key, "hub")

    async def test_inbound_messages(self) -> None:
        hub = ConcreteHub(name="hub")
        c1 = ConcreteComponent(name="c1", hub=hub)
        await hub.add_component(c1)
        c2 = ConcreteComponent(name="c2", hub=hub)
        await hub.add_component(c2)

        await hub.inbound_event(evt := NewComponent())
        await hub.inbound_broadcast(brd := Shutdown())
        await hub.inbound_command(
            cmd := SetPower(power=1, dst=build_routing_keys(["hub.c2"]))
        )

        assert c1.received == [evt, brd]
        assert c2.received == [evt, brd, cmd]
