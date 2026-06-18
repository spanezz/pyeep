import unittest
from typing import override

from pyeep.models.color import Color
from pyeep.nodes.groups import Group, GroupDescription, Groups
from pyeep.nodes.messages import ComponentAdded, ComponentRemoved
from pyeep.test.components import ConcreteWebHub


def groupdesc(
    name: str = "group",
    label: str | None = None,
    icon: str = "G",
    color: Color = Color(red=1, green=0.5, blue=0.3),
    match: list[str] = [],
) -> GroupDescription:
    return GroupDescription(
        name=name,
        label=label or name.capitalize(),
        icon=icon,
        color=color,
        match=match,
    )


class GroupTestCase(unittest.IsolatedAsyncioTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.hub = ConcreteWebHub(name="hub")

    def group(self, desc: GroupDescription) -> Group:
        return Group(desc=desc, hub=self.hub)


class TestGroup(GroupTestCase):
    def test_init(self) -> None:
        group = self.group(groupdesc())
        self.assertEqual(group.name, "group")
        self.assertEqual(group.routing_key, "hub.group")

    async def test_match_literal(self) -> None:
        group = self.group(groupdesc(match=["foo", "bar"]))
        self.assertEqual(group.members, set())
        await group.receive(ComponentAdded(src="foo"))
        self.assertEqual(group.members, {"foo"})
        await group.receive(ComponentAdded(src="bar"))
        self.assertEqual(group.members, {"foo", "bar"})
        await group.receive(ComponentRemoved(src="foo"))
        self.assertEqual(group.members, {"bar"})

        # Idempotence
        await group.receive(ComponentAdded(src="bar"))
        self.assertEqual(group.members, {"bar"})
        await group.receive(ComponentRemoved(src="foo"))
        self.assertEqual(group.members, {"bar"})

    async def test_dst(self) -> None:
        group = self.group(groupdesc(match=["foo", "bar"]))
        await group.receive(ComponentAdded(src="foo"))
        await group.receive(ComponentAdded(src="bar"))
        self.assertCountEqual(group.dst(), ("foo", "bar"))


class TestGroups(GroupTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.groups = Groups(name="groups", hub=self.hub)

    async def test_load(self) -> None:
        data = [
            groupdesc(name="group1").model_dump(),
            groupdesc(name="group2").model_dump(),
        ]
        await self.groups.load(data)
        self.assertCountEqual(self.groups.groups.keys(), ("group1", "group2"))
        group1 = self.groups.groups["group1"]
        group2 = self.groups.groups["group2"]
        self.assertIs(self.hub.components[group1.routing_key], group1)
        self.assertIs(self.hub.components[group2.routing_key], group2)

    async def test_dst(self) -> None:
        data = [
            groupdesc(name="group1").model_dump(),
            groupdesc(name="group2").model_dump(),
        ]
        await self.groups.load(data)
        self.groups.groups["group1"].members.update(("foo", "bar"))
        self.groups.groups["group2"].members.update(("bar", "baz"))
        self.assertCountEqual(
            self.groups.dst("group1", "group2"), ("foo", "bar", "baz")
        )
