from pyeep.nodes.messages import (
    ComponentAdded,
    ComponentRemoved,
    HubConnected,
    Shutdown,
)
from pyeep.test.messages import BroadcastTestCase, EventTestCase


class TestShutdown(BroadcastTestCase[Shutdown]):
    message_cls = Shutdown
    samples = {"shutdown": Shutdown()}


class TestHubConnected(BroadcastTestCase[HubConnected]):
    message_cls = HubConnected
    samples = {"connected": HubConnected()}


class TestComponentAdded(EventTestCase[ComponentAdded]):
    message_cls = ComponentAdded
    samples = {"new": ComponentAdded()}


class TestComponentRemoved(EventTestCase[ComponentRemoved]):
    message_cls = ComponentRemoved
    samples = {"removed": ComponentRemoved()}
