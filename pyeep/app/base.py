import abc
import argparse
import contextlib
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


class BaseApp(contextlib.ExitStack):
    """Base framework for executable commands."""

    def __init__(self) -> None:
        super().__init__()
        parser = self.argparser()
        self.args = parser.parse_args()

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

    def main_init(self) -> None:
        """Initialize the application before entering the main loop."""
        self.setup_logging()

    @abc.abstractmethod
    def main_loop(self) -> None:
        """
        Main loop.

        The application will shut down after this function returns.
        """

    def main_shutdown(self) -> None:
        """Shut down the application."""

    def main(self) -> None:
        """Main entry point for the application."""
        with self:
            self.main_init()
            try:
                self.main_loop()
            finally:
                self.main_shutdown()

    @classmethod
    def run(cls) -> None:
        """Instantiate and run the app."""
        app = cls()
        app.main()
