import asyncio
from typing import override, Unpack

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import AppEvent, BaseAppArgs

from .jack import JackClient, MIDIHandler, MIDIInput
from .messages import MIDIMessage, MIDIMessages
from .midisynth import setup_synth


class AppEventMIDI(AppEvent):
    def __init__(self, *, frame_time: int, messages: list[MIDIMessage]) -> None:
        self.frame_time = frame_time
        self.messages = messages


class NotifyMIDIEvents(MIDIHandler):
    """Copy messages from JACK to the main event loop."""

    def __init__(
        self,
        *,
        name: str = "NotifyMIDIEvents",
        queue: asyncio.Queue[AppEvent],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(name=name)
        self.queue = queue
        self.loop = loop

    @override
    def midi_process(self, messages: list[MIDIMessage]) -> None:
        # NOTE: this runs in JACK's realtime thread
        frame_time = self.midi_input.jack_client.last_frame_time
        asyncio.run_coroutine_threadsafe(
            self.queue.put(
                AppEventMIDI(frame_time=frame_time, messages=messages)
            ),
            self.loop,
        )


class MidiSynth(ApplicationAsyncCmdClientApp):
    """MIDI synthetizer."""

    def __init__(self, **kwargs: Unpack[BaseAppArgs]) -> None:
        super().__init__(**kwargs)
        self.jack = JackClient(self.name, log=self.log)
        self.midi_input = MIDIInput()
        self.jack.add_handler(self.midi_input)
        setup_synth(self.jack, self.midi_input)

    @override
    async def main_process_event(self, evt: AppEvent) -> None:
        match evt:
            case AppEventMIDI():
                await self.send_event(
                    MIDIMessages(
                        frame_time=evt.frame_time, messages=evt.messages
                    )
                )
                # for idx, msg in enumerate(evt.messages, start=1):
                #     self.log.info(
                #         "MIDI event %d/%d: %s", idx, len(evt.messages), msg
                #     )
            case _:
                await super().main_process_event(evt)

    @override
    async def start_main_tasks(self) -> None:
        notify_midi_events = NotifyMIDIEvents(
            queue=self.main_event_queue, loop=asyncio.get_running_loop()
        )
        self.midi_input.add_handler(notify_midi_events)
        await super().start_main_tasks()
        await self.start_task(self.jack.main())


if __name__ == "__main__":
    MidiSynth.run()
