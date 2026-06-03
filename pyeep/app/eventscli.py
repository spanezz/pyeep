import asyncio
import cmd
import os
import signal
import threading
from typing import override

import rich

from pyeep.app.client import ClientApp
from pyeep.app.base import AppEvent, AppShutdownEvent
from pyeep.component.component import Component
from pyeep.models.messages import Message
from pyeep.models.messages.power import SetGroupPower, IncreaseGroupPower


class EventsComponent(Component):
    pass


class RemoteQuit(Exception):
    """Exception raised when the remote has quit."""


class EventsCli(cmd.Cmd):
    def __init__(self):
        super().__init__()
        self.events = EventsComponent(name="events")
        self.app = ClientApp(name="eventscli", handle_sigterm_sigint=False)
        self.app.webclient.add_component(self.events)
        self.log = self.app.log
        self.app_thread: threading.Thread | None = None
        self.loop: asyncio.EventLoop | None = None
        self.loop_available = threading.Event()
        #: Set to True when the user explicitly asked to quit
        self.pid = os.getpid()
        self.quit_requested: bool = False
        signal.signal(signal.SIGTERM, self.on_sigterm)

    def on_sigterm(self, signal: signal.Signals, frame) -> None:
        raise RemoteQuit()

    async def async_app_thread(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.loop_available.set()
        await self.app.main()
        current_task = asyncio.current_task()
        if pending_tasks := [
            t for t in asyncio.all_tasks() if t != current_task
        ]:
            try:
                await asyncio.wait(pending_tasks, timeout=3)
            except TimeoutError:
                self.log.error("Timed out waiting for leftover tasks to finish")
        self.loop = None
        self.app_thread = None

    def app_thread_main(self) -> None:
        try:
            asyncio.run(self.async_app_thread())
        except Exception as e:
            self.log.error("Exception in async thread: %s", e, exc_info=e)
        if not self.quit_requested:
            self.log.info(
                "Remote closed the connection, sending SIGTERM to the main thread"
            )
            os.kill(self.pid, signal.SIGTERM)

    def notify_app(self, event: AppEvent) -> None:
        if self.loop is None:
            raise AssertionError(
                "Cannot notify app before the event loop has started"
            )
        asyncio.run_coroutine_threadsafe(
            self.app.main_event_queue.put(event), self.loop
        )

    def send_message(self, message: Message) -> None:
        self.log.info("Sending %s", message)
        if self.loop is None:
            raise AssertionError(
                "Cannot notify app before the event loop has started"
            )
        asyncio.run_coroutine_threadsafe(self.events.send(message), self.loop)

    def run(self) -> None:
        self.app_thread = threading.Thread(target=self.app_thread_main)
        self.app_thread.start()
        self.loop_available.wait()
        try:
            self.cmdloop()
        except RemoteQuit:
            pass
        finally:
            if self.app_thread is not None:
                self.notify_app(AppShutdownEvent("User quit"))
                self.app_thread.join()

    def do_quit(self, arg) -> None:
        self.quit_requested = True
        return True

    def do_EOF(self, arg) -> None:
        self.quit_requested = True
        return True

    def do_power(self, arg) -> None:
        args = arg.split()
        group = int(args[0])
        if (value := args[1]).startswith("+"):
            self.send_message(
                IncreaseGroupPower(group=group, amount=int(value[1:]))
            )
        else:
            self.send_message(SetGroupPower(group=group, power=int(value)))


def main():
    eventscli = EventsCli()
    eventscli.run()


if __name__ == "__main__":
    main()
