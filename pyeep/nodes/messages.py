from pyeep.models.messages.message import Broadcast, Event


class Shutdown(Broadcast):
    """Notify that the Hub is shutting down."""


class HubConnected(Broadcast):
    """Notify that the Hub is connected."""


class ComponentAdded(Event):
    """
    Notify that a new component has been added.

    The new component is identified by ``self.src``.
    """


class ComponentRemoved(Event):
    """
    Notify that a component has been removed.

    The component is identified by ``self.src``.
    """
