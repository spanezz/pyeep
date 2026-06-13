from typing import override

import jack
import mido
import numpy as np

from pyeep.midisynth.synth.midisynth import (
    MidiSynth,
    AudioConfig,
    Instruments,
)
from pyeep.midisynth.synth.midisynth import EnvelopeShape, Sine, Saw
from pyeep.midisynth import synth
from .jack import JackClient, JackHandler, MIDIHandler, MIDIInput, MIDIMessage


class AudioOut(JackHandler):
    def __init__(
        self, *, name: str = "synth_audio_out", synth: synth.midisynth.MidiSynth
    ) -> None:
        super().__init__(name=name)
        self.synth = synth
        self.outport: jack.Port
        # self.debug_outfile = open("jack.np", "wb")

    @override
    def register(self, client: "JackClient") -> None:
        super().register(client)
        self.outport = client.jack_client.outports.register(self.name)
        # Connect to audio output ports
        port_name: str | None = None
        for port in self.jack_client.get_ports(
            is_physical=True, is_audio=True, is_input=True
        ):
            name = port.name.split(":", 1)[0]
            if port_name is None:
                port_name = name
            elif port_name != name:
                break
            self.jack_client.connect(self.outport, port)

    @override
    def jack_process(self, frames: int) -> None:
        assert hasattr(self.outport, "get_array")
        arr = self.outport.get_array()
        arr[:] = 0
        self.synth.generate(self.jack_client.last_frame_time, arr)
        # arr.tofile(self.debug_outfile)


class MIDIIn(MIDIHandler):
    def __init__(
        self, *, name: str = "synth_midi_in", synth: synth.midisynth.MidiSynth
    ) -> None:
        super().__init__(name=name)
        self.synth = synth

    @override
    def midi_process(self, messages: list[MIDIMessage]) -> None:
        assert messages
        last_frame_time = self.midi_input.jack_client.last_frame_time
        mido_messages: list[mido.Message] = [
            mido.Message.from_bytes(msg.message, time=msg.frame_time)
            for msg in messages
        ]
        self.synth.add_messages(last_frame_time, mido_messages)


def setup_synth(jack_client: JackClient, midi_input: MIDIInput) -> None:
    rate = jack_client.samplerate
    midi_synth = MidiSynth(in_samplerate=rate)

    # Set up the synth instrument bank
    instruments = Instruments(
        AudioConfig(
            in_samplerate=rate,
            out_samplerate=rate,
            dtype=np.float32,
        )
    )
    envelope = EnvelopeShape(
        attack_time=0.03, decay_time=0.01, release_time=0.1
    )
    instruments.set(0, Sine, envelope=envelope)
    instruments.set(1, Saw, envelope=envelope)
    midi_synth.add_output(instruments)

    audio_out = AudioOut(synth=midi_synth)
    midi_in = MIDIIn(synth=midi_synth)

    midi_input.add_handler(midi_in)
    jack_client.add_handler(audio_out)
