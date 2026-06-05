import abc
import asyncio
import argparse
import logging
from typing import override

from prompt_toolkit import PromptSession, Application
from prompt_toolkit.document import Document
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import containers
from prompt_toolkit.layout import controls
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit import widgets

from pyeep.app.base import AppShutdownEvent
from pyeep.app.client import ClientApp
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.happylights.happylights import HappyLights
from pyeep.models.messages.color import SetGroupColor


class AsyncCmdQuit(BaseException):
    """Exception raised when the Cmd should quit."""


class AsyncCmd(abc.ABC):
    """Interactive shell."""

    def __init__(self) -> None:
        #: Default prompt
        self.prompt: str = "> "
        #: Commands defined as do_* methods in the class
        self.commands: list[str] = [
            name[3:] for name in dir(self.__class__) if name.startswith("do_")
        ]

    @abc.abstractmethod
    async def prompt_user(self) -> str:
        """Prompt the user and return the line they entered."""

    @abc.abstractmethod
    async def print_error(self, message: str) -> None:
        """Output an error message."""

    async def get_prompt(self) -> str:
        """
        Return the user prompt.

        This is ``self.prompt`` by default, but you can override this function
        to make a more dynamic prompt.
        """
        return self.prompt

    async def default(self, command: str, args: str | None) -> None:
        """Handle commands that do not have a ``do_*`` method."""
        await self.print_error(f"*** Unknown command: {command}")

    async def handle_eof(self) -> None:
        """Handle EOF on input."""
        raise AsyncCmdQuit()

    async def handle_line(self, line: str) -> None:
        """Hande a line entered by the user."""
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
        """Input REPL loop."""
        try:
            while True:
                try:
                    line = await self.prompt_user()
                except EOFError:
                    await self.handle_eof()
                else:
                    await self.handle_line(line)
        except AsyncCmdQuit:
            pass


class PromptSessionAsyncCmd(AsyncCmd):
    """Concrete AsyncCmd based on PromptSession."""

    def __init__(self) -> None:
        super().__init__()
        self.session: PromptSession[str] = PromptSession(
            completer=WordCompleter(self.commands)
        )

    @override
    async def prompt_user(self) -> str:
        with patch_stdout():
            return await self.session.prompt_async(await self.get_prompt())

    @override
    async def print_error(self, message: str) -> None:
        print(message)


class ApplicationAsyncCmd(AsyncCmd):
    """Concrete AsyncCmd based on Application."""

    def __init__(self) -> None:
        super().__init__()
        self.term_text: list[tuple[str, str]] = []
        self.term = controls.FormattedTextControl(
            style="class:output-field",
            text=[("#ff00ff", "Welcome.\n")],
        )
        self.term_window = containers.Window(content=self.term)
        self.cmdline = widgets.TextArea(
            height=1,
            prompt=self.prompt,
            style="class:input-field",
            multiline=False,
            wrap_lines=False,
            completer=WordCompleter(self.commands),
        )
        self.cmdline.accept_handler = self.accept_line
        root_container = containers.HSplit(
            [
                self.term_window,
                widgets.HorizontalLine(),
                self.cmdline,
            ]
        )
        layout = Layout(root_container, focused_element=self.cmdline)

        kb = KeyBindings()

        @kb.add("c-c")
        @kb.add("c-q")
        @kb.add("c-d")
        def _(event):
            "Pressing Ctrl-Q or Ctrl-C will exit the user interface."
            event.app.exit()

        style = Style(
            [
                ("output-field", "bg:#000044 #ffffff"),
                ("input-field", "bg:#000000 #ffffff"),
                ("line", "#004400"),
            ]
        )

        self.application: Application[str] = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            mouse_support=True,
            full_screen=True,
        )

    async def accept_line_async(self, line: str) -> None:
        await self.term_print(f"> {line}")

        try:
            await self.handle_line(line)
        except AsyncCmdQuit:
            self.application.exit()

    def accept_line(self, buffer: Buffer) -> bool:
        asyncio.run_coroutine_threadsafe(
            self.accept_line_async(buffer.text), asyncio.get_running_loop()
        )
        return False

    async def term_print(
        self, message: str, style: str = "#dddddd", end="\n"
    ) -> None:
        self.term_text += [(style, message + end)]
        self.term_text = self.term_text[-50:]
        self.term.text = self.term_text + [("[SetCursorPosition]", "")]

    @override
    async def prompt_user(self) -> str:
        raise NotImplementedError("Prompting is done in another way")

    @override
    async def print_error(self, message: str) -> None:
        await self.term_print(message, style="#ff0000")

    @override
    async def async_cmdloop(self) -> None:
        await self.application.run_async()


# class LightsCmd(PromptSessionAsyncCmd):
class LightsCmd(ApplicationAsyncCmd):
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
        await self.cmd.term_print(f"Color set to {color}.", style=str(color))


if __name__ == "__main__":
    LightsApp.run()
