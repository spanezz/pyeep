import asyncio
import abc
import inspect
import logging
import time as tm
from typing import override, Callable

from prompt_toolkit import PromptSession, Application
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import containers
from prompt_toolkit.layout import controls
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit import widgets, application

from pyeep.app.base import AppShutdownEvent
from pyeep.app.client import ClientApp


class AsyncCmdQuit(BaseException):
    """Exception raised when the Cmd should quit."""


class AsyncCmd(abc.ABC):
    """Interactive shell."""

    def __init__(self, handler_object: object | None = None) -> None:
        """
        Initialize an AsyncCmd.

        :param handler_object: object that will be used to lookup cmd_* methods.
          Defaults to ``self``
        """
        #: Default prompt
        self.prompt: str = "> "
        #: Object that contains the cmd_* methods
        self.handler_object = (
            handler_object if handler_object is not None else self
        )
        #: Commands defined as cmd_* methods in the class
        self.commands: dict[str, Callable[[str], None]] = {
            name[4:]: handler
            for name, handler in inspect.getmembers(
                self.handler_object, inspect.iscoroutinefunction
            )
            if name.startswith("cmd_")
        }

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
        """Handle commands that do not have a ``cmd_*`` method."""
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

        if (handler := self.commands.get(command)) is None:
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
            completer=WordCompleter(self.commands.keys())
        )

    @override
    async def prompt_user(self) -> str:
        with patch_stdout():
            return await self.session.prompt_async(await self.get_prompt())

    @override
    async def print_error(self, message: str) -> None:
        print(message)


class MessagesControl(controls.FormattedTextControl):
    """Display a scrolling line-based list of messages."""

    def __init__(self) -> None:
        super().__init__()
        self.term_lines: list[list[tuple[str, str]]] = []

    def add_line(self, line: list[tuple[str, str]]) -> None:
        self.term_lines.append(line)
        # TODO: clip to the actual term window height
        # TODO: or clip to the screen height if we cannot get the term window
        #       height
        self.term_lines = self.term_lines[-50:]
        contents: list[tuple[str, str]] = []
        for line in self.term_lines:
            contents.extend(line)
            contents.append(("", "\n"))
        contents.append(("[SetCursorPosition]", ""))
        self.text = contents
        if app := application.current.get_app_or_none():
            app.invalidate()


class ApplicationAsyncCmd(AsyncCmd):
    """Concrete AsyncCmd based on Application."""

    def __init__(self, handler_object: object | None = None) -> None:
        """
        Initialize an ApplicationAsyncCmd.

        :param handler_object: object that will be used to lookup cmd_* methods
        """
        super().__init__(handler_object=handler_object)
        self.term = MessagesControl()
        self.term_window = containers.Window(content=self.term)
        self.cmdline = widgets.TextArea(
            height=1,
            prompt=self.prompt,
            style="class:input-field",
            multiline=False,
            wrap_lines=False,
            completer=WordCompleter(self.commands.keys()),
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
                ("input-field", "bg:#000000 #ffffff"),
                ("error", "#dd0000"),
                ("log-time", "#7777ff"),
                ("log-path", "#bbbbbb"),
                ("log-name", "#77cccc"),
                ("log-level-notset", "#555555"),
                ("log-level-debug", "#00aa00"),
                ("log-level-info", "#77aa00"),
                ("log-level-warning", "#cccc00"),
                ("log-level-error", "#dd0000"),
                ("log-level-critical", "#dd0000 bold"),
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
        self.term.add_line([("", f"> {line}")])

        try:
            await self.handle_line(line)
        except AsyncCmdQuit:
            self.application.exit()

    def accept_line(self, buffer: Buffer) -> bool:
        asyncio.run_coroutine_threadsafe(
            self.accept_line_async(buffer.text), asyncio.get_running_loop()
        )
        return False

    @override
    async def prompt_user(self) -> str:
        raise NotImplementedError("Prompting is done in another way")

    @override
    async def print_error(self, message: str) -> None:
        self.term.add_line([("#ff0000", message)])

    @override
    async def async_cmdloop(self) -> None:
        await self.application.run_async()


class ApplicationAsyncCmdLogHandler(logging.Handler):
    """Log handler for colored log output."""

    def __init__(
        self, level: int | str = logging.NOTSET, *, term: MessagesControl
    ) -> None:
        super().__init__(level)
        self.term = term

    @override
    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)

        time = (
            "class:log-time",
            tm.strftime("%H:%M:%S", tm.localtime(record.created)),
        )
        logname = ("class:log-name", record.name)
        fname = ("class:log-path", f"{record.filename}:{record.lineno}")
        level_name = record.levelname
        level = (f"class:log-level-{level_name.lower()}", level_name)

        self.term.add_line(
            [
                time,
                ("", " "),
                logname,
                ("", " "),
                fname,
                ("", " "),
                level,
                ("", " "),
                ("", message),
            ]
        )


class ApplicationAsyncCmdClientApp(ClientApp):
    """Client App with an ApplicationAsyncCmd interface."""

    def __init__(
        self, *, name: str, handle_sigterm_sigint: bool = True
    ) -> None:
        super().__init__(name=name, handle_sigterm_sigint=handle_sigterm_sigint)
        self.interface = ApplicationAsyncCmd(handler_object=self)

    @override
    def setup_logging(self):
        """Set up the logging module for this application."""
        FORMAT = "%(name)s %(message)s"
        if self.args.debug:
            log_level = logging.DEBUG
        elif self.args.verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        logging.basicConfig(
            level=log_level,
            handlers=[ApplicationAsyncCmdLogHandler(term=self.interface.term)],
            format=FORMAT,
        )

    async def main_cmd_task(self) -> None:
        await self.cmd_help(None)
        await self.interface.async_cmdloop()
        await self.main_event_queue.put(AppShutdownEvent("User quit"))

    @override
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        await super().start_main_tasks(tg)
        tg.create_task(self.main_cmd_task())

    async def cmd_quit(self, arg) -> None:
        """Quit the program."""
        raise AsyncCmdQuit()

    async def cmd_help(self, arg) -> None:
        """Show available commands."""
        if arg is None:
            self.interface.term.add_line(
                [
                    ("", "Welcome to "),
                    ("bold", self.name),
                    ("", ". Commands available:"),
                ]
            )
            self.interface.term.add_line([])
            for name, handler in sorted(self.interface.commands.items()):
                if handler.__doc__ is None:
                    summary = "Description not available."
                else:
                    summary = handler.__doc__.strip().split("\n", 1)[0].strip()
                self.interface.term.add_line(
                    [("", "* "), ("bold", name), ("", ": "), ("", summary)]
                )
        elif (handler := self.interface.commands.get(arg)) is None:
            self.interface.term.add_line(
                [("class:error", f"Command {arg!r} not found.")]
            )
        else:
            for line in inspect.getdoc(handler).splitlines():
                self.interface.term.add_line([("", line)])
