import threading
import logging
import argparse
import asyncio
import os
from typing import override, Unpack, Literal

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import AppEvent, BaseAppArgs

from . import messages

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402


class JoystickInfo:
    def __init__(self, js: pygame.joystick.JoystickType) -> None:
        self.js = js
        self.instance_id = js.get_instance_id()
        self.name = js.get_name()

    def removed_event(self) -> messages.JoystickRemoved | None:
        return messages.JoystickRemoved(
            instance_id=self.instance_id, name=self.name
        )

    def axis_name(self, axis: int) -> str:
        return str(axis)

    def axis_event(
        self, evt: pygame.event.Event
    ) -> messages.JoystickEvent | None:
        return messages.JoystickTriggerEvent(
            instance_id=self.instance_id,
            name=self.name,
            trigger=self.axis_name(evt.axis),
            value=evt.value,
        )

    def hat_name(self, hat: int) -> str:
        return str(hat)

    def button_name(self, button: int) -> str:
        return str(button)

    def button_event(
        self, evt: pygame.event.Event
    ) -> messages.JoystickButtonEvent | None:
        state: Literal["down", "up"]
        match evt.type:
            case pygame.JOYBUTTONDOWN:
                state = "down"
            case pygame.JOYBUTTONUP:
                state = "up"
            case _:
                return None

        return messages.JoystickButtonEvent(
            instance_id=self.instance_id,
            name=self.name,
            button=self.button_name(evt.button),
            state=state,
        )

    def hat_event(
        self, evt: pygame.event.Event
    ) -> messages.JoystickHatEvent | None:
        return messages.JoystickHatEvent(
            instance_id=self.instance_id,
            name=self.name,
            hat=self.hat_name(evt.hat),
            x=evt.value[0],
            y=evt.value[1],
        )


class Stick:
    def __init__(
        self, joystick_info: JoystickInfo, name: str, dead_zone: float
    ) -> None:
        self.joystick_info = joystick_info
        self.name = name
        self.dead_zone = dead_zone
        self.x = 0.0
        self.y = 0.0
        self.changed: bool = True

    def adjust_value(self, value: float) -> float:
        if abs(value) < self.dead_zone:
            return 0
        return value

    def x_value(self, value: float) -> None:
        if (x := self.adjust_value(value)) != self.x:
            self.x = x
            self.changed = True

    def y_value(self, value: float) -> None:
        if (y := self.adjust_value(value)) != self.y:
            self.y = y
            self.changed = True

    def stick_event(self) -> messages.JoystickStickEvent | None:
        if not self.changed:
            return None
        self.changed = False
        return messages.JoystickStickEvent(
            instance_id=self.joystick_info.instance_id,
            name=self.joystick_info.name,
            stick=self.name,
            x=self.x,
            y=self.y,
        )


class Xbox360JoystickInfo(JoystickInfo):
    AXIS_NAMES: dict[int, str] = {
        0: "LX",
        1: "LY",
        2: "LT",
        3: "RX",
        4: "RY",
        5: "RT",
    }
    HAT_NAMES: dict[int, str] = {0: "DPAD"}
    BUTTON_NAMES: dict[int, str] = {
        0: "A",
        1: "B",
        2: "X",
        3: "Y",
        4: "LB",
        5: "RB",
        6: "BACK",
        7: "START",
        8: "HOME",
        9: "LS",
        10: "RS",
    }
    DEAD_ZONE_LS = 0.42
    DEAD_ZONE_RS = 0.42

    def __init__(self, js: pygame.joystick.JoystickType) -> None:
        super().__init__(js)
        self.ls = Stick(self, "LS", self.DEAD_ZONE_LS)
        self.rs = Stick(self, "RS", self.DEAD_ZONE_RS)

    @override
    def axis_name(self, axis: int) -> str:
        return self.AXIS_NAMES.get(axis, str(axis))

    def adjust_ls_value(self, value: float) -> float:
        if abs(value) < self.DEAD_ZONE_LS:
            return 0
        return value

    def adjust_rs_value(self, value: float) -> float:
        if abs(value) < self.DEAD_ZONE_RS:
            return 0
        return value

    @override
    def axis_event(
        self, evt: pygame.event.Event
    ) -> messages.JoystickEvent | None:
        match evt.axis:
            case 0:
                self.ls.x_value(evt.value)
                return self.ls.stick_event()
            case 1:
                self.ls.y_value(evt.value)
                return self.ls.stick_event()
            case 3:
                self.rs.x_value(evt.value)
                return self.rs.stick_event()
            case 4:
                self.rs.y_value(evt.value)
                return self.rs.stick_event()
            case 2 | 5:
                return messages.JoystickTriggerEvent(
                    instance_id=self.instance_id,
                    name=self.name,
                    trigger=self.axis_name(evt.axis),
                    value=evt.value,
                )
            case _:
                return None

    @override
    def hat_name(self, hat: int) -> str:
        return self.HAT_NAMES.get(hat, str(hat))

    @override
    def button_name(self, button: int) -> str:
        return self.BUTTON_NAMES.get(button, str(button))


JOYSTICK_INFO_CLS: dict[str, type[JoystickInfo]] = {
    "Xbox 360 Controller": Xbox360JoystickInfo
}


class AppEventJoystick(AppEvent):
    def __init__(self, message: messages.JoystickEvent) -> None:
        self.message = message


class AppEvent1DAxisMotion(AppEvent):
    def __init__(self, instance_id: int, axis: str, value: float) -> None:
        self.instance_id = instance_id
        self.axis = axis
        self.value = value


class AppEvent2DAxisMotion(AppEvent):
    def __init__(self, instance_id: int, axis: str, x: float, y: float) -> None:
        self.instance_id = instance_id
        self.axis = axis
        self.x = x
        self.y = y


class ReadGamepad(threading.Thread):
    """Read messages from the gamepad."""

    def __init__(
        self,
        *,
        queue: asyncio.Queue[AppEvent],
        loop: asyncio.AbstractEventLoop,
        log: logging.Logger,
    ) -> None:
        super().__init__()
        self.queue = queue
        self.loop = loop
        self.log = log
        self.joysticks: dict[int, JoystickInfo] = {}

    def notify_app(self, event: AppEvent) -> None:
        """Send an AppEvent to the main app."""
        asyncio.run_coroutine_threadsafe(self.queue.put(event), self.loop)

    def make_joystick_info(
        self, js: pygame.joystick.JoystickType
    ) -> JoystickInfo:
        ji_cls = JOYSTICK_INFO_CLS.get(js.get_name(), JoystickInfo)
        return ji_cls(js)

    def add_joystick(self, js: pygame.joystick.JoystickType) -> None:
        self.joysticks[js.get_instance_id()] = self.make_joystick_info(js)
        self.notify_app(
            AppEventJoystick(
                messages.JoystickAdded(
                    instance_id=js.get_instance_id(), name=js.get_name()
                )
            )
        )

    @override
    def run(self) -> None:
        try:
            self.main()
        except Exception as exc:
            self.log.error("Exception in pygame thread: %s", exc, exc_info=exc)

    def main(self) -> None:
        pygame.display.init()
        pygame.joystick.init()
        for idx in range(pygame.joystick.get_count()):
            self.add_joystick(pygame.joystick.Joystick(idx))

        while True:
            event = pygame.event.wait()
            match event.type:
                case pygame.QUIT:
                    break
                case pygame.JOYDEVICEADDED:
                    self.add_joystick(pygame.joystick.Joystick(idx))
                case pygame.JOYDEVICEREMOVED:
                    if ji := self.joysticks.pop(event.instance_id, None):
                        if rmsg := ji.removed_event():
                            self.notify_app(AppEventJoystick(rmsg))
                case pygame.JOYAXISMOTION:
                    if ji := self.joysticks.get(event.instance_id):
                        if amsg := ji.axis_event(event):
                            self.notify_app(AppEventJoystick(amsg))
                case pygame.JOYBUTTONDOWN | pygame.JOYBUTTONUP:
                    if ji := self.joysticks.get(event.instance_id):
                        if bmsg := ji.button_event(event):
                            self.notify_app(AppEventJoystick(bmsg))
                case pygame.JOYHATMOTION:
                    if ji := self.joysticks.get(event.instance_id):
                        if hmsg := ji.hat_event(event):
                            self.notify_app(AppEventJoystick(hmsg))
                case _:
                    self.log.info("Ingnoring pygame event: %s", event)

    def quit(self) -> None:
        """Signal that the pygame loop should quit."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))


class Gamepad(ApplicationAsyncCmdClientApp):
    """Gamepad-based event generator."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.reader: ReadGamepad | None = None

    @override
    async def main_process_event(self, evt: AppEvent) -> None:
        match evt:
            case AppEventJoystick():
                self.log.info("Joystick event: %s", evt.message)
                await self.send_event(evt.message)
            case _:
                await super().main_process_event(evt)

    @override
    async def main_init(self) -> None:
        await super().main_init()
        self.reader = ReadGamepad(
            queue=self.main_event_queue,
            loop=asyncio.get_running_loop(),
            log=self.log,
        )

    @override
    async def main_welcome_user(self) -> None:
        await super().main_welcome_user()
        assert self.reader is not None
        self.reader.start()

    @override
    async def main_shutdown(self) -> None:
        if self.reader is not None:
            # File a QUIT event to the pygame thread
            self.reader.quit()
            await asyncio.to_thread(self.reader.join)

        await super().main_shutdown()

    # async def cmd_mute(self) -> None:
    #     self.synth.mute()

    # async def cmd_unmute(self) -> None:
    #     self.synth.unmute()


if __name__ == "__main__":
    Gamepad.run()
