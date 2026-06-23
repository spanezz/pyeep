from typing import Literal

from pyeep.models.messages import Event


class JoystickEvent(Event):
    """Base for joystick/gamepad events."""

    #: Unique identifier of the device in the system
    instance_id: int
    #: Device name
    name: str


class JoystickAdded(JoystickEvent):
    """A joystick has been added to the system."""


class JoystickRemoved(JoystickEvent):
    """A joystick has been removed from the system."""


class JoystickButtonEvent(JoystickEvent):
    """Joystick button event."""

    #: Button name
    button: str
    #: Button action reported
    state: Literal["down", "up"]


class JoystickStickEvent(JoystickEvent):
    """Joystick analog 2D axis event."""

    #: Stick name
    stick: str
    #: X value (-1 to 1)
    x: float
    #: Y value (-1 to 1)
    y: float


class JoystickTriggerEvent(JoystickEvent):
    """Joystick analog 1D axis event."""

    #: Trigger name
    trigger: str
    #: Value (-1 to 1)
    value: float


class JoystickHatEvent(JoystickEvent):
    """Joystick hat event."""

    #: Hat name
    hat: str
    #: X value (-1 to 1)
    x: int
    #: Y value (-1 to 1)
    y: int
