import unittest

from pyeep.models.messages.message import Broadcast, Command, Event, Message
from pyeep.models.messages.routing import (
    build_routing_keys,
    expand_routing_keys,
)
from pyeep.test.messages import (
    BroadcastTestCase,
    CommandTestCase,
    EventTestCase,
    MessageTestCase,
)


class TestRoutingKeys(unittest.TestCase):
    def test_build_routing_keys(self) -> None:
        for inp, expected in (
            (["a"], ("a",)),
            (["a.b"], ("a.b",)),
            (
                ["A", "A.B.C", "A.D", "1.2.3"],
                ("A", "A.B.C", "A.D", "1.2.3"),
            ),
        ):
            with self.subTest(inp=str(inp)):
                assert build_routing_keys(inp) == expected

    def test_expand_routing_keys(self) -> None:
        nodes = ["A", "AB1", "AB2", "AC", "AC1", "AC2"]
        rks = build_routing_keys(tuple(rk) for rk in nodes)
        assert list("".join(rk) for rk in expand_routing_keys(rks)) == nodes

    # def test_route_down_nodes(self) -> None:
    #     def brks(*nodes: str) -> RoutingKeys:
    #         return build_routing_keys(tuple(rk) for rk in nodes)

    #     self.assertEqual(route_down((), None), (True, []))
    #     self.assertEqual(route_down((), {"": None}), (True, []))
    #     self.assertEqual(route_down(("A",), None), (False, []))
    #     self.assertEqual(route_down(("A",), {"": None}), (False, []))
    #     self.assertEqual(route_down(("A",), brks("B", "C")), (False, []))
    #     self.assertEqual(
    #         route_down(("A",), brks("AB", "AC")), (False, ["B", "C"])
    #     )
    #     print(brks("A", "AB", "AC"))
    #     self.assertEqual(
    #         route_down(("A",), brks("A", "AB", "AC")), (True, ["B", "C"])
    #     )


class TestMessage(MessageTestCase[Message]):
    message_cls = Message
    samples = {"message": Message()}

    def test_members(self) -> None:
        m = self.samples["message"]
        self.assertEqual(m.primitive, "pyeep.models.messages.message.Message")
        self.assertIsInstance(m.ts, int)
        self.assertIsNone(m.src)


class TestEvent(EventTestCase[Event]):
    message_cls = Event
    samples = {"event": Event()}


class TestBroadcast(BroadcastTestCase[Broadcast]):
    message_cls = Broadcast
    samples = {"broadcast": Broadcast()}


class TestCommand(CommandTestCase[Command]):
    message_cls = Command
    sample_rks = build_routing_keys(["a.b", "a.b.c", "b.d"])
    samples = {
        "no_targets": Command(dst=()),
        "targets": Command(dst=sample_rks),
    }

    def test_members(self) -> None:
        self.assertEqual(self.samples["no_targets"].dst, ())
        self.assertEqual(self.samples["targets"].dst, self.sample_rks)
