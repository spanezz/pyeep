from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import logging
import threading

try:
    import coloredlogs
    HAVE_COLOREDLOGS = True
except ModuleNotFoundError:
    HAVE_COLOREDLOGS = False


class App(contextlib.ExitStack):
    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.shutting_down = False

    @classmethod
    def argparser(self, description: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="verbose output")
        parser.add_argument("--debug", action="store_true",
                            help="verbose output")
        return parser

    def shutdown(self):
        self.shutting_down = True

    def setup_logging(self):
        FORMAT = "%(levelname)s %(name)s %(message)s"
        if self.args.debug:
            log_level = logging.DEBUG
        elif self.args.verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        if coloredlogs is not None:
            coloredlogs.install(level=log_level, fmt=FORMAT)
        else:
            logging.basicConfig(level=log_level, stream=sys.stderr, format=FORMAT)

    async def aio_main(self):
        pass

    def ui_main(self):
        pass

    def _aio_thread(self):
        asyncio.run(self.aio_main())

    def main(self):
        self.setup_logging()
        aio_thread = threading.Thread(target=self._aio_thread, name="aio")
        aio_thread.start()
        try:
            self.ui_main()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
            aio_thread.join()
