import abc
import asyncio
import concurrent
import os
import signal
import threading
from typing import Coroutine

from pyeep.app.client import ClientApp
from pyeep.app.base import AppEvent, AppShutdownEvent
from pyeep.models.messages import Message


class RemoteQuit(Exception):
    """Exception raised when the remote has quit."""


class SyncClientApp(abc.ABC):
    """
    pyeep app supporting a non-async event loop.

    This runs as two threads: the main thread running an abstract sync method
    and a separate thread running the asyncio event loop and all the rest of
    the app.
    """

    def __init__(self, *, app: ClientApp) -> None:
        self.app = app
        self.log = self.app.log
        self.app_thread: threading.Thread | None = None
        self.loop: asyncio.EventLoop | None = None
        self.loop_available = threading.Event()
        #: Set to True when the user explicitly asked to quit
        self.pid = os.getpid()
        #: Set to True when the app quit has been initiated from the main
        #: thread
        self.quit_requested_by_main_thread: bool = False
        # TODO: move to run
        signal.signal(signal.SIGTERM, self.on_sigterm_sigint)
        signal.signal(signal.SIGINT, self.on_sigterm_sigint)

    def on_sigterm_sigint(self, signal: signal.Signals, frame) -> None:
        raise RemoteQuit()

    async def app_thread_async_main(self) -> None:
        """Main async function of the asyncio event loop thread."""
        # Make a reference to the event loop available to the main thread
        self.loop = asyncio.get_running_loop()
        self.loop_available.set()

        # Run the app
        await self.app.main()

        # Process leftover tasks
        current_task = asyncio.current_task()
        if pending_tasks := [
            t for t in asyncio.all_tasks() if t != current_task
        ]:
            try:
                await asyncio.wait(pending_tasks, timeout=3)
            except TimeoutError:
                self.log.error("Timed out waiting for leftover tasks to finish")

    def app_thread_main(self) -> None:
        """Main function of the asyncio event loop thread."""
        try:
            asyncio.run(self.app_thread_async_main())
        except Exception as e:
            self.log.error("Exception in async thread: %s", e, exc_info=e)
        finally:
            # Let the main thread see that the async thread has quit
            self.loop = None
            self.app_thread = None
            if not self.quit_requested_by_main_thread:
                self.log.info(
                    "Remote closed the connection,"
                    " sending SIGTERM to the main thread"
                )
                os.kill(self.pid, signal.SIGTERM)

    def run_async[T](
        self, coro: Coroutine[None, None, T]
    ) -> concurrent.futures.Future[T]:
        """Run a coroutine in the async thread."""
        if self.loop is None:
            raise AssertionError(
                "Cannot notify app before the event loop has started"
            )
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def notify_app(self, event: AppEvent) -> None:
        """Enqueue an AppEvent in the App event queue."""
        self.run_async(self.app.main_event_queue.put(event))

    def send(self, message: Message) -> None:
        """Send a message via the app."""
        self.log.info("Sending %s", message)
        self.run_async(self.app.send(message))

    def run(self) -> None:
        self.app_thread = threading.Thread(target=self.app_thread_main)
        self.app_thread.start()
        self.loop_available.wait()
        try:
            self.main()
        except RemoteQuit:
            pass
        finally:
            self.quit_requested_by_main_thread = True
            if self.app_thread is not None:
                self.notify_app(AppShutdownEvent("User quit"))
                self.app_thread.join()

    @abc.abstractmethod
    def main(self) -> None:
        """Main function."""
