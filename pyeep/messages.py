from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .component.base import Component


class Message:
    """
    Base class for messages sent between components
    """
    def __init__(
            self, *,
            ts: float | None = None,
            src: Component | None = None,
            dst: str | None = None,
            name: str | None = None):
        self.ts = ts
        self.src = src
        self.dst = dst
        if name is None:
            self.name = self.__class__.__name__.lower()
        else:
            self.name = name

    def __str__(self) -> str:
        return self.name


class Shutdown(Message):
    """
    Message sent to initiate component shutdown
    """
    pass


class EmergencyStop(Message):
    """
    Request to stop any activity as soon as possible
    """
    pass


class DeviceScanRequest(Message):
    """
    Request to scan for new devices
    """
    def __init__(self, *, duration: float, **kwargs):
        super().__init__(**kwargs)
        # Duration in seconds of the scan
        self.duration = duration

    def __str__(self):
        return super().__str__() + f"(duration={self.duration})"


class Shortcut(Message):
    """
    Event notifying the trigger of a named keyboard shortcut
    """
    def __init__(self, *, command: str, **kwargs):
        super().__init__(**kwargs)
        self.command = command

    def __str__(self):
        return super().__str__() + f"(command={self.command})"


class Pause(Message):
    """
    Pause outputs in a group
    """
    def __init__(self, *, group: int, **kwargs):
        super().__init__(**kwargs)
        self.group = group

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group})"


class Resume(Message):
    """
    Unpause outputs in a group
    """
    def __init__(self, *, group: int, **kwargs):
        super().__init__(**kwargs)
        self.group = group

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group})"


class NewComponent(Message):
    """
    Notify that a new component has been added
    """
    def __str__(self) -> str:
        return super().__str__() + f"(component={self.src})"


class ComponentActiveStateChanged(Message):
    """
    Notify a change of active state for an input
    """
    def __init__(self, *, value: bool, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    def __str__(self) -> str:
        return super().__str__() + f"(value={self.value})"
