from typing import override
from unittest import TestCase

from pyeep.nodes import Node


class ConcreteNode(Node):
    @override
    def get_routing_key(self) -> str:
        return f"test.{self.name}"


class TestNode(TestCase):
    def test_routing_key(self) -> None:
        node = ConcreteNode(name="foo")
        self.assertEqual(node.routing_key, "test.foo")

    def test_logger(self) -> None:
        node = ConcreteNode(name="foo")
        self.assertEqual(node.log.name, "foo")

    def test_str(self) -> None:
        node = ConcreteNode(name="foo")
        self.assertEqual(str(node), "foo")
