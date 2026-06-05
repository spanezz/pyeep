import asyncio
import argparse
import logging
from typing import override

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

from pyeep.app.base import AppShutdownEvent
from pyeep.app.client import ClientApp
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.happylights.happylights import HappyLights
from pyeep.models.messages.color import SetGroupColor


class AsyncCmdQuit(BaseException):
    """Exception raised when the Cmd should quit."""


class AsyncCmd:
    def __init__(self) -> None:
        self.prompt: str = "> "
        commands = [
            name[3:] for name in dir(self.__class__) if name.startswith("do_")
        ]
        self.session: PromptSession[str] = PromptSession(
            completer=WordCompleter(commands)
        )

    async def print_error(self, message: str) -> None:
        print(message)

    async def default(self, command: str, args: str | None) -> None:
        await self.print_error(f"*** Unknown command: {command}")

    async def handle_eof(self) -> None:
        raise AsyncCmdQuit()

    async def handle_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return

        parts = line.split(None, 1)
        command = parts[0]
        if len(parts) == 1:
            args = None
        else:
            args = parts[1]

        if (handler := getattr(self, f"do_{command}", None)) is None:
            await self.default(command, args)
        else:
            try:
                await handler(args)
            except Exception as e:
                await self.print_error(str(e))

    async def async_cmdloop(self) -> None:
        try:
            while True:
                try:
                    with patch_stdout():
                        line = await self.session.prompt_async(self.prompt)
                except EOFError:
                    await self.handle_eof()
                else:
                    await self.handle_line(line)
        except AsyncCmdQuit:
            pass


class LightsCmd(AsyncCmd):
    """Interactive lights control."""

    def __init__(self, lights_app: "LightsApp") -> None:
        super().__init__()
        self.lights_app = lights_app

    async def do_quit(self, arg) -> None:
        raise AsyncCmdQuit()

    async def do_color(self, arg) -> None:
        r, g, b = [float(a) for a in arg.split()]
        await self.lights_app.set_color(Color(red=r, green=g, blue=b))


class LightsApp(ClientApp):
    """Control a happylights bluetooth light source."""

    def __init__(
        self, *, name: str = "happylights", handle_sigterm_sigint: bool = True
    ) -> None:
        super().__init__(name=name, handle_sigterm_sigint=handle_sigterm_sigint)
        self.lights: HappyLights | None = None
        if self.args.addr:
            self.lights = HappyLights(
                device=self.args.addr, log=logging.getLogger(f"{self.name}.ble")
            )
        self.cmd = LightsCmd(self)

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument(
            "--addr", "-a", type=str, help="Bluetooth address of the device"
        )
        return parser

    async def cmd_task(self) -> None:
        await self.cmd.async_cmdloop()
        await self.main_event_queue.put(AppShutdownEvent("User quit"))

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        if self.lights is not None:
            tg.create_task(self.lights.main())
        tg.create_task(self.cmd_task())

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case SetGroupColor():
                # TODO: actual animator support
                # TODO: match group
                await self.set_color(Color(red=0.5, green=0, blue=0))

    async def set_color(self, color: Color) -> None:
        if self.lights is not None:
            await self.lights.set_color(Color(red=0.5, green=0, blue=0))
            await asyncio.sleep(0.3)
            await self.lights.set_color(Color(red=0, green=0, blue=0))


if __name__ == "__main__":
    LightsApp.run()
