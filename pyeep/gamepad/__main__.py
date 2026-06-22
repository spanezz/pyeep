import threading
import logging
import argparse
import asyncio
import os
from typing import override, Unpack, NamedTuple

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import AppEvent, BaseAppArgs

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame


class JoystickInfo:
    def __init__(self, js: pygame.joystick.JoystickType) -> None:
        self.js = js
        self.instance_id = js.get_instance_id()
        self.name = js.get_name()

    def axis_name(self, axis: int) -> str:
        return str(axis)

    def axis_event(
        self, evt: pygame.event.Event
    ) -> "AppEventAxisMotion | None":
        return AppEventAxisMotion(
            evt.instance_id, self.axis_name(evt.axis), evt.value
        )

    def hat_name(self, hat: int) -> str:
        return str(hat)

    def button_name(self, button: int) -> str:
        return str(button)


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
        8: "XBOX",
        9: "LS",
        10: "RS",
    }
    DEAD_ZONE_LS = 0.42
    DEAD_ZONE_RS = 0.42

    @override
    def axis_name(self, axis: int) -> str:
        return self.AXIS_NAMES.get(axis, str(axis))

    @override
    def axis_event(
        self, evt: pygame.event.Event
    ) -> "AppEventAxisMotion | None":
        match evt.axis:
            case 0 | 1:
                if abs(evt.value) < self.DEAD_ZONE_LS:
                    return None
            case 3 | 4:
                if abs(evt.value) < self.DEAD_ZONE_RS:
                    return None
        return super().axis_event(evt)

    @override
    def hat_name(self, hat: int) -> str:
        return self.HAT_NAMES.get(hat, str(hat))

    @override
    def button_name(self, button: int) -> str:
        return self.BUTTON_NAMES.get(button, str(button))


JOYSTICK_INFO_CLS: dict[str, type[JoystickInfo]] = {
    "Xbox 360 Controller": Xbox360JoystickInfo
}


class AppEventJoystickAdded(AppEvent):
    def __init__(self, instance_id: int, name: str) -> None:
        self.instance_id = instance_id
        self.name = name


class AppEventJoystickRemoved(AppEvent):
    def __init__(self, instance_id: int) -> None:
        self.instance_id = instance_id


class AppEventButtonDown(AppEvent):
    def __init__(self, instance_id: int, button: str) -> None:
        self.instance_id = instance_id
        self.button = button


class AppEventButtonUp(AppEvent):
    def __init__(self, instance_id: int, button: str) -> None:
        self.instance_id = instance_id
        self.button = button


class AppEventAxisMotion(AppEvent):
    def __init__(self, instance_id: int, axis: str, value: float) -> None:
        self.instance_id = instance_id
        self.axis = axis
        self.value = value


class AppEventHatMotion(AppEvent):
    def __init__(self, instance_id: int, hat: str, x: int, y: int) -> None:
        self.instance_id = instance_id
        self.hat = hat
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
            AppEventJoystickAdded(js.get_instance_id(), js.get_name())
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
                    self.joysticks.pop(event.instance_id, None)
                    self.notify_app(AppEventJoystickRemoved(event.instance_id))
                case pygame.JOYAXISMOTION:
                    if ji := self.joysticks.get(event.instance_id):
                        if evt := ji.axis_event(event):
                            self.notify_app(evt)
                case pygame.JOYBUTTONDOWN:
                    if ji := self.joysticks.get(event.instance_id):
                        self.notify_app(
                            AppEventButtonDown(
                                event.instance_id, ji.button_name(event.button)
                            )
                        )
                    else:
                        self.log.info("NO JS?")
                case pygame.JOYBUTTONUP:
                    if ji := self.joysticks.get(event.instance_id):
                        self.notify_app(
                            AppEventButtonUp(
                                event.instance_id, ji.button_name(event.button)
                            )
                        )
                case pygame.JOYHATMOTION:
                    if ji := self.joysticks.get(event.instance_id):
                        self.notify_app(
                            AppEventHatMotion(
                                event.instance_id,
                                ji.hat_name(event.hat),
                                x=event.value[0],
                                y=event.value[1],
                            )
                        )
                case _:
                    self.log.info("pygame event: %s", event)

                    # if components := self.event_map.get(event.type):
                    #     for c in components:
                    #         c.pygame_event(event)

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
            # TODO: send pyeep events
            case AppEventJoystickAdded():
                self.log.info(
                    "Joystick %d added: %s", evt.instance_id, evt.name
                )
            case AppEventJoystickRemoved():
                self.log.info("Joystick %d removed", evt.instance_id)
            case AppEventButtonDown():
                self.log.info(
                    "Joystick %d button down %s", evt.instance_id, evt.button
                )
            case AppEventButtonUp():
                self.log.info(
                    "Joystick %d button up %s", evt.instance_id, evt.button
                )
            case AppEventAxisMotion():
                self.log.info(
                    "Joystick %d button axis %s value %f",
                    evt.instance_id,
                    evt.axis,
                    evt.value,
                )
            case AppEventHatMotion():
                self.log.info(
                    "Joystick %d button hat %s value x:%d y: %d",
                    evt.instance_id,
                    evt.hat,
                    evt.x,
                    evt.y,
                )
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
