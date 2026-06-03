import asyncio
import abc
import argparse
import functools
import signal
import logging
import time as tm
from typing import override

import rich
import rich.text


class ColoredLogHandler(logging.Handler):
    """Log handler for colored log output."""

    def __init__(self, level: int | str = logging.NOTSET) -> None:
        super().__init__(level)
        self.console = rich.get_console()

    def format_level(self, record: logging.LogRecord) -> rich.text.Text:
        """Format the logging level."""
        # Taken from rich.logging.RichHandler.get_level_text
        level_name = record.levelname
        level_text = rich.text.Text.styled(
            level_name.ljust(8), f"logging.level.{level_name.lower()}"
        )
        return level_text

    @override
    def emit(self, record: logging.LogRecord) -> None:
        message = rich.markup.escape(self.format(record))

        time = rich.text.Text.styled(
            tm.strftime("%H:%M:%S", tm.localtime(record.created)), "log.time"
        )
        fname = rich.text.Text.styled(
            rich.markup.escape(f"{record.filename}:{record.lineno}".ljust(25)),
            "log.path",
        )
        level = self.format_level(record)

        self.console.print(
            time,
            fname,
            level,
            message,
            highlight=False,
        )


class AppEvent:
    """Base class for events used to control app flow."""


class AppShutdownEvent(AppEvent):
    """App shutdown requested."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    @override
    def __str__(self) -> str:
        return self.reason


class BaseApp:
    """Base framework for executable commands."""

    def __init__(self, *, name: str) -> None:
        """
        Initialize an app.

        :param name: application name (used in logging)
        """
        self.name = name
        self.log = logging.getLogger(f"app.{self.name}")
        parser = self.argparser()
        self.args = parser.parse_args()
        self.main_event_queue: asyncio.Queue[AppEvent] = asyncio.Queue()

    def argparser(
        self, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description=description or self.__doc__.strip()
        )
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="verbose output"
        )
        parser.add_argument(
            "--debug", action="store_true", help="verbose output"
        )
        return parser

    def setup_logging(self):
        """
        Set up the logging module for this application
        """
        FORMAT = "%(name)s %(message)s"
        if self.args.debug:
            log_level = logging.DEBUG
        elif self.args.verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        logging.basicConfig(
            level=log_level, handlers=[ColoredLogHandler()], format=FORMAT
        )

    def handle_termination_signal(
        self, signum: signal.Signals
    ) -> asyncio.Task[None]:
        """Signal handler for termination signals."""

        async def handler() -> None:
            reason = f"Signal {signum} ({signum.name}) received"
            self.log.info("%s", reason)
            await self.main_event_queue.put(AppShutdownEvent(reason))

        return asyncio.create_task(handler())

    async def main_init(self) -> None:
        """Initialize the application before entering the main loop."""
        self.setup_logging()
        for signum in signal.SIGINT, signal.SIGTERM:
            asyncio.get_running_loop().add_signal_handler(
                signum,
                functools.partial(self.handle_termination_signal, signum),
            )

    @abc.abstractmethod
    async def start_main_tasks(self, tg: asyncio.TaskGroup) -> None:
        """
        Start tasks for the application.

        Start the tasks via the task group; the application will exit when the
        task group exists.
        """

    async def main_shutdown_requested(self) -> None:
        """Callen when an app shutdown has been requested."""

    async def main_shutdown(self) -> None:
        """Shut down the application."""

    async def main(self) -> None:
        """Main entry point for the application."""

        class Shutdown(Exception):
            """Shutdown has been requested."""

        await self.main_init()
        try:
            async with asyncio.TaskGroup() as tg:
                await self.start_main_tasks(tg)
                while True:
                    evt = await self.main_event_queue.get()
                    self.log.debug("App event: %s", evt)
                    match evt:
                        case AppShutdownEvent():
                            await self.main_shutdown_requested()
                            # Raise an exception instead of breaking out of the
                            # while, so that tasks in tg are cancelled
                            self.main_event_queue.task_done()
                            raise Shutdown(str(evt))
                        case _:
                            self.log.warning(
                                "Received unsupported app event: %s", evt
                            )
                    self.main_event_queue.task_done()
        except* Shutdown as exc:
            self.log.info("App shutdown: %s", exc.exceptions[0])
        finally:
            await self.main_shutdown()

    @classmethod
    def run(cls) -> None:
        """Instantiate and run the app."""
        app = cls()
        asyncio.run(app.main())
