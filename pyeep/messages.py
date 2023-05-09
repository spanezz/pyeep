from __future__ import annotations

from .app import Message


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
