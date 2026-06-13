import asyncio
import abc
import logging
import threading
from typing import override
from .messages import MIDIMessage

import jack


class JackHandler(abc.ABC):
    """Handler that runs in JackClient's process function."""

    jack_client: jack.Client

    def __init__(self, *, name: str) -> None:
        """
        Initialize a JackHandler.

        :param name: name to use to identify the handler
        """
        self.name = name

    def register(self, client: "JackClient") -> None:
        """Set the JACK client when this handler is registered."""
        self.jack_client = client.jack_client

    @abc.abstractmethod
    def jack_process(self, frames: int) -> None:
        """
        JACK process function.

        This runs in JACK's realtime thread.
        """

    def jack_xrun(self, delayed_usecs: float) -> None:
        """Notify a JACK xrun."""
        # Do nothing by default

    def jack_samplerate(self, samplerate: int) -> None:
        """Notify a JACK samplerate change."""
        # Do nothing by default


class HandlerFailed:
    """Signal that a handler process function failed."""

    def __init__(self, handler: JackHandler, exc: Exception) -> None:
        self.handler = handler
        self.exc = exc


class JackClient:
    """Wrap a Jack Client allowing to hook multiple process functions."""

    def __init__(self, jack_name: str, log: logging.Logger) -> None:
        """
        Initialize a JackClient.

        :param jack_name: Jack client name
        """
        self.name = jack_name
        self.log = log
        self.jack_handlers: list[JackHandler] = []
        self.jack_handlers_lock = threading.Lock()
        self.jack_client = jack.Client(self.name)
        self.jack_client.set_process_callback(self.jack_process)
        self.jack_client.set_xrun_callback(self.jack_xrun)
        self.jack_client.set_samplerate_callback(self.jack_samplerate)
        self.samplerate = self.jack_client.samplerate
        self.failed_queue: asyncio.Queue[HandlerFailed] = asyncio.Queue()
        self.aioloop: asyncio.AbstractEventLoop

    def _notify_failed_handler(self, handler: JackHandler, exc: Exception):
        asyncio.run_coroutine_threadsafe(
            self.failed_queue.put(HandlerFailed(handler, exc)), self.aioloop
        )

    def jack_xrun(self, delayed_usecs: float) -> None:
        """
        Handle a xrun.

        This runs in a jack non-realtime thread.
        """
        self.log.warning("JACK xrun %fµsecs", delayed_usecs)
        with self.jack_handlers_lock:
            for handler in self.jack_handlers:
                handler.jack_xrun(delayed_usecs)

    def jack_samplerate(self, samplerate: int) -> None:
        """
        Handle a samplerate change.

        This runs in a jack non-realtime thread.
        """
        self.log.warning("JACK samplerate changed to %d", samplerate)
        with self.jack_handlers_lock:
            for handler in self.jack_handlers:
                handler.jack_samplerate(samplerate)

    def jack_process(self, frames: int):
        """
        JACK process function.

        This runs in JACK's realtime thread.
        """
        with self.jack_handlers_lock:
            for handler in self.jack_handlers:
                try:
                    handler.jack_process(frames)
                except Exception as exc:
                    self._notify_failed_handler(handler, exc)

    def add_handler(self, handler: JackHandler) -> None:
        """
        Add a JACK handler to be called in the JACK process function.

        The function is idempotent: adding a handler multiple times is the same
        as adding it only once.
        """
        with self.jack_handlers_lock:
            if handler not in self.jack_handlers:
                handler.register(self)
                self.jack_handlers.append(handler)

    def remove_handler(self, handler: JackHandler) -> None:
        """
        Remove a JACK handler.

        If it is not present, nothing will happen.
        """
        with self.jack_handlers_lock:
            try:
                self.jack_handlers.remove(handler)
            except ValueError:
                pass

    async def main(self) -> None:
        """Connect to Jack and run handlers."""
        self.aioloop = asyncio.get_running_loop()
        with self.jack_client:
            self.log.info("JACK client started")
            while True:
                evt = await self.failed_queue.get()
                self.log.error(
                    "JACK handler %s failed: %s",
                    evt.handler.name,
                    evt.exc,
                    exc_info=evt.exc,
                )
                self.remove_handler(evt.handler)


class MIDIHandler(abc.ABC):
    """Handler that processes incoming MIDI messages."""

    def __init__(self, *, name: str) -> None:
        """
        Initialize a MIDIHandler.

        :param name: name to use to identify the handler
        """
        self.name = name

    def register(self, midi_input: "MIDIInput") -> None:
        """Set the MIDI input when this handler is registered."""
        self.midi_input = midi_input

    @abc.abstractmethod
    def midi_process(self, messages: list[MIDIMessage]) -> None:
        """
        Process an incoming MIDI message.

        This runs in JACK's realtime thread.
        """


class MIDIInput(JackHandler):
    """JACK handler dispatching MIDI input."""

    def __init__(self, name: str = "MIDI input") -> None:
        """
        Initialize a MIDI input.

        :param name: Pyeep JackHandler name.
        """
        super().__init__(name=name)

    @override
    def register(self, client: "JackClient") -> None:
        super().register(client)
        self.inport = self.jack_client.midi_inports.register(self.name)
        self.midi_handlers: list[MIDIHandler] = []
        self.midi_handlers_lock = threading.Lock()
        # Connect to all midi output ports
        for port in self.jack_client.get_ports(is_midi=True, is_output=True):
            self.jack_client.connect(port, self.inport)

    def add_handler(self, handler: MIDIHandler) -> None:
        """
        Add a MIDI handler to be called in the JACK process function.

        The function is idempotent: adding a handler multiple times is the same
        as adding it only once.
        """
        with self.midi_handlers_lock:
            if handler not in self.midi_handlers:
                handler.register(self)
                self.midi_handlers.append(handler)

    @override
    def jack_process(self, frames: int):
        assert hasattr(self.inport, "incoming_midi_events")
        messages: list[MIDIMessage] = []
        frame_time = self.jack_client.last_frame_time
        for offset, indata in self.inport.incoming_midi_events():
            messages.append(MIDIMessage(frame_time + offset, bytes(indata)))
        if not messages:
            return

        with self.midi_handlers_lock:
            for handler in self.midi_handlers:
                handler.midi_process(messages)
