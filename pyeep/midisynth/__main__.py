import argparse
import asyncio
from typing import override, Unpack

from pyeep.app.asynccmd import ApplicationAsyncCmdClientApp
from pyeep.app.base import AppEvent, BaseAppArgs

from .jack import JackClient, MIDIHandler, MIDIInput
from .messages import MIDIMessage, MIDIMessages
from .midisynth import Synth


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
        self.synth = Synth(self.jack, mute=self.args.mute)

    @override
    @classmethod
    def argparser(
        cls, description: str | None = None
    ) -> argparse.ArgumentParser:
        parser = super().argparser(description)
        parser.add_argument("--mute", action="store_true", help="Start muted")
        return parser

    @override
    async def main_process_event(self, evt: AppEvent) -> None:
        match evt:
            case AppEventMIDI():
                await self.send_event(
                    MIDIMessages(
                        frame_time=evt.frame_time,
                        sample_rate=self.jack.samplerate,
                        messages=evt.messages,
                    )
                )
                # for idx, msg in enumerate(evt.messages, start=1):
                #     self.log.info(
                #         "MIDI event %d/%d: %s", idx, len(evt.messages), msg
                #     )
            case _:
                await super().main_process_event(evt)

    @override
    async def init(self) -> None:
        notify_midi_events = NotifyMIDIEvents(
            queue=self.main_event_queue, loop=asyncio.get_running_loop()
        )
        self.synth.midi_input.add_handler(notify_midi_events)
        await super().init()
        await self.start_task(self.jack.main())

    @override
    async def main_welcome_user(self) -> None:
        await super().main_welcome_user()
        if self.args.mute:
            self.log.info("Starting muted.")

    async def cmd_mute(self) -> None:
        self.synth.mute()

    async def cmd_unmute(self) -> None:
        self.synth.unmute()


if __name__ == "__main__":
    MidiSynth.run()
