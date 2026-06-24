import abc
from typing import override, Unpack, Literal

import evdev
from evdev import ecodes

# from pyeep.models.messages.input import EmergencyStop, Shortcut
from .device import Device, DeviceArgs
from .messages import KeyEvent

# To avoid devices being registered as normal keyboard, and make them
# accessible exclusively to the user running pyeep, you need to install udev
# rules to that effect.
#
# See https://www.enricozini.com/blog/2023/debian/handling-keyboard-like-devices/
# for examples and documentation
#
# General evdev information: https://wiki.archlinux.org/title/Keyboard_input


class KeyboardDevice(Device, abc.ABC):
    KEY_MAP: dict[int, str]

    def make_message(self, evt: evdev.InputEvent) -> KeyEvent | None:
        """Create a message from the given keyboard event."""
        if evt.type != ecodes.EV_KEY:
            return None
        action: Literal["up", "down"]
        match evt.value:
            case 0:
                action = "up"
            case 1:
                action = "down"
            case _:
                return None
        if (name := self.KEY_MAP.get(evt.code)) is None:
            return None
        return KeyEvent(key=name, action=action)


class CNCControlPanel(
    KeyboardDevice, register={"usb-04d9_1203-event-kbd": "cnc"}
):
    """
    Handle key presses from a CNC control panel
    """

    # this has been tested with
    # https://www.amazon.com/Engraving-Controller-Handwheel-Electronic-Handbrake/dp/B09CMKRYTP
    KEY_MAP = {
        ecodes.KEY_GRAVE: "EMERGENCY",
        # InputEvent(EV_KEY, KEY_LEFTALT, 1)
        ecodes.KEY_R: "CYCLE START",
        ecodes.KEY_F5: "SPINDLE ON/OFF",
        # InputEvent(EV_KEY, KEY_RIGHTCTRL, 1)
        ecodes.KEY_W: "REDO",
        # InputEvent(EV_KEY, KEY_LEFTALT, 1)
        ecodes.KEY_N: "SINGLE STEP",
        # InputEvent(EV_KEY, KEY_LEFTCTRL, 1)
        ecodes.KEY_O: "ORIGIN POINT",
        ecodes.KEY_ESC: "STOP",
        ecodes.KEY_KPPLUS: "SPEED UP",
        ecodes.KEY_KPMINUS: "SLOW DOWN",
        ecodes.KEY_F11: "F+",
        ecodes.KEY_F10: "F-",
        ecodes.KEY_RIGHTBRACE: "J+",
        ecodes.KEY_LEFTBRACE: "J-",
        ecodes.KEY_UP: "+Y",
        ecodes.KEY_DOWN: "-Y",
        ecodes.KEY_LEFT: "-X",
        ecodes.KEY_RIGHT: "+X",
        ecodes.KEY_KP7: "+A",
        ecodes.KEY_Q: "-A",
        ecodes.KEY_PAGEDOWN: "-Z",
        ecodes.KEY_PAGEUP: "+Z",
    }

    @override
    async def on_evdev(self, evt: evdev.InputEvent) -> None:
        if (msg := self.make_message(evt)) is None:
            return
        # if name == "EMERGENCY":
        #    self.send(EmergencyStop())
        #    return
        await self.send_event(msg)


class PageTurner(
    KeyboardDevice,
    register={"bluetooth-40:44:fa:66:08:b8:16-kbd": "pageturner"},
):
    """
    Handle button presses from a Bluetooth page turner
    """

    # This has been tested with https://www.amazon.it/dp/B0BPJJTV39
    KEY_MAP = {
        ecodes.KEY_UP: "PREVIOUS",
        ecodes.KEY_DOWN: "NEXT",
        ecodes.KEY_LEFT: "PREVIOUS",
        ecodes.KEY_RIGHT: "NEXT",
    }

    @override
    async def on_evdev(self, evt: evdev.InputEvent) -> None:
        if (msg := self.make_message(evt)) is None:
            return
        await self.send_event(msg)


class Gesture:
    def __init__(self) -> None:
        self.start_x: int | None = None
        self.start_y: int | None = None
        self.last_x: int | None = None
        self.last_y: int | None = None
        self.motion_threshold = 500

    def report_x(self, value: int) -> bool:
        """
        Report a motion in the X coordinate.

        :returns: True if X moved more than a threshold.
        """
        if self.start_x is None:
            self.start_x = value
        else:
            self.last_x = value
            if abs(self.last_x - self.start_x) > self.motion_threshold:
                return True
        return False

    def report_y(self, value: int) -> bool:
        """
        Report a motion in the Y coordinate.

        :returns: True if Y moved more than a threshold.
        """
        if self.start_y is None:
            self.start_y = value
        else:
            self.last_y = value
            if abs(self.last_y - self.start_y) > self.motion_threshold:
                return True
        return False

    def delta(self, start: int | None, end: int | None) -> int:
        if start is None or end is None:
            return 0
        return end - start

    def name(self) -> str:
        delta_x = self.delta_x
        delta_y = self.delta_y
        if delta_y < -self.motion_threshold:
            return "DOWN"
        elif delta_y > self.motion_threshold:
            return "UP"
        elif delta_x < -self.motion_threshold:
            return "DOWN2"
        elif delta_x > self.motion_threshold:
            return "UP2"
        else:
            return "CLICK"

    @property
    def delta_x(self) -> int:
        return self.delta(self.start_x, self.last_x)

    @property
    def delta_y(self) -> int:
        return self.delta(self.start_y, self.last_y)

    @override
    def __str__(self) -> str:
        return (
            f"x:{self.delta(self.start_x, self.last_x)}"
            f" y:{self.delta(self.start_y, self.last_y)}"
        )


class RingRemote(
    Device, register={"bluetooth-22c:44:fa:66:08:b8:16-tablet": "ring"}
):
    """
    Handle events from a Bluetooth tiktok scroll ring
    """

    # This has been tested with https://www.amazon.it/dp/B0BZC85G7F
    def __init__(self, **kwargs: Unpack[DeviceArgs]) -> None:
        super().__init__(**kwargs)
        self.gesture: Gesture | None = None

    def _process_event(self, evt: evdev.InputEvent) -> str | None:
        """
        Process an event, returning a shortcut name if one triggered
        """
        # See /usr/include/linux/input-event-codes.h

        # https://github.com/LinusCDE/rmTabletDriver/blob/master/tabletDriver.py
        # BTN_TOOL_PEN == 1 means that the pen is hovering over the tablet
        # BTN_TOUCH == 1 means that the pen is touching the tablet

        match evt.type:
            case ecodes.EV_SYN:
                # Ignored
                pass
            case ecodes.EV_MSC:
                # Ignored
                pass
            case ecodes.EV_KEY:
                match evt.code:
                    case ecodes.BTN_TOOL_PEN:
                        # Ignored
                        pass
                    case ecodes.BTN_TOUCH:
                        match evt.value:
                            case 1:
                                # Gesture start
                                if self.gesture is not None:
                                    self.log.warning(
                                        "Gesture aborted replaced with a new one"
                                    )
                                self.gesture = Gesture()
                            case 0:
                                # Gesture end
                                if self.gesture is None:
                                    # Gesture already processed during EV_ABS events
                                    pass
                                else:
                                    name = self.gesture.name()
                                    self.gesture = None
                                    return name
                            case _:
                                self.log.warning(
                                    "Unknown BTN_TOOL_PEN event: %s", evt
                                )
            case ecodes.EV_ABS:
                # A full up/down gesture takes about 0.3s, a left/right gesture
                # about 0.24, while a click around 0.03s. A simulated vertical
                # shift of 500 takes around 0.07s, a simulated horizontal shift
                # of 500 takes around 0.05s.
                #
                # We can cut down latency by detecting that a delta x o y is
                # above a threshold, and ignore all further events until a
                # BTN_TOUCH up
                match evt.code:
                    case ecodes.ABS_X:
                        if self.gesture is None:
                            # Ignore
                            pass
                            # self.log.warning(
                            #     "ABS_X event without a gesture started: %s", evt
                            # )
                        else:
                            if self.gesture.report_x(evt.value):
                                name = self.gesture.name()
                                self.gesture = None
                                return name
                    case ecodes.ABS_Y:
                        if self.gesture is None:
                            # Ignore
                            pass
                            # self.log.warning(
                            #     "ABS_Y event without a gesture started: %s", evt
                            # )
                        else:
                            if self.gesture.report_y(evt.value):
                                name = self.gesture.name()
                                self.gesture = None
                                return name
                    case _:
                        self.log.warning("Unknown ABS event %s", evt)
            case _:
                self.log.warning("Unknown event %s", evt)
        return None

    @override
    async def on_evdev(self, ev: evdev.InputEvent) -> None:
        if (shortcut := self._process_event(ev)) is None:
            return
        await self.send_event(KeyEvent(key=shortcut, action="down"))
        await self.send_event(KeyEvent(key=shortcut, action="up"))
