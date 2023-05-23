from __future__ import annotations

import jack
import mido

from ..component.aio import AIOComponent
from ..component.jack import JackComponent
from ..messages import Message


class MidiMessage(Message):
    def __init__(self, msg: mido.Message, **kwargs):
        super().__init__(**kwargs)
        self.msg = msg

    def __str__(self) -> str:
        return super().__str__() + f"(msg={self.msg})"


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
            # TODO
            messages.append(msg)

        self.hub.loop.call_soon_threadsafe(self._send_mido_messages, messages)

    def _send_mido_messages(self, messages: list[mido.Message]):
        for msg in messages:
            self.send(MidiMessage(msg=msg))
