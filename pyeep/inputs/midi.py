from __future__ import annotations

import jack
import mido

from ..component.aio import AIOComponent
from ..component.jack import JackComponent
from ..messages import Message


class MidiMessages(Message):
    def __init__(self, last_frame_time: int, frames: int, messages: list[mido.Message], **kwargs):
        super().__init__(**kwargs)
        self.last_frame_time = last_frame_time
        self.frames = frames
        self.messages = messages

    def __str__(self) -> str:
        return super().__str__() + (
                f"(last_frame_time={self.last_frame_time},"
                f" frames={self.frames},"
                f" messages={self.messages})")


class MidiInput(JackComponent, AIOComponent):
    def set_jack_client(self, jack_client: jack.Client):
        super().set_jack_client(jack_client)
        self.inport = self.jack_client.midi_inports.register('midi input')

    def jack_process(self, frames: int):
        messages: list[mido.Message] = []
        frame_time = self.jack_client.last_frame_time
        for offset, indata in self.inport.incoming_midi_events():
            msg = mido.parse([ord(b) for b in indata])
            msg.time = frame_time + offset
            messages.append(msg)

        if not messages:
            return

        # TODO: as a future optimization, the message could be left somewhere
        # where other jack_process callbacks can find it, to reduce latency

        self.hub.loop.call_soon_threadsafe(
                self.send, MidiMessages(
                    last_frame_time=frame_time, frames=frames, messages=messages))
