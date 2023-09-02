from __future__ import annotations

import jack
import numpy

from ..component.aio import AIOComponent
from ..component.jack import JackComponent
from ..inputs.midi import MidiMessages
from ..messages.component import Shutdown
from .. import midisynth
from .base import Output


class Synth(Output, JackComponent, AIOComponent):
    def __init__(self, **kwargs):
        super().__init__(rate=0, **kwargs)
        # TODO: jack has a RingBuffer class for this
        self.synth: midisynth.MidiSynth
        self.instruments: midisynth.Instruments

    def jack_add_messages(self, msg: MidiMessages):
        """
        Enqueue notes to be played.

        This function is called from the Jack realtime thread
        """
        self.synth.add_messages(
                msg.last_frame_time,
                msg.messages)

    def set_jack_client(self, jack_client: jack.Client):
        super().set_jack_client(jack_client)

        # Direcly hook this as a MIDI consumer that gets messages from the MIDI
        # input in the RT thread
        reader = self.hub.app.get_component("midiinput")
        reader.add_midi_sink(self.jack_add_messages)

        self.outport = self.jack_client.outports.register('synth')
        self.set_rate(jack_client.samplerate)

        self.synth = midisynth.MidiSynth(in_samplerate=self.rate)

        # Set up the synth instrument bank
        self.instruments = midisynth.Instruments(
                midisynth.AudioConfig(
                    in_samplerate=self.rate,
                    out_samplerate=self.rate,
                    dtype=numpy.float32))
        envelope = midisynth.EnvelopeShape(attack_time=0.03, decay_time=0.01, release_time=0.1)
        self.instruments.set(0, midisynth.Sine, envelope=envelope)
        self.instruments.set(1, midisynth.Saw, envelope=envelope)
        self.synth.add_output(self.instruments)

    def jack_process(self, frames: int) -> None:
        self.instruments.generate(
                    self.jack_client.last_frame_time,
                    self.outport.get_array())

    async def run(self) -> None:
        while True:
            msg = await self.next_message()
            match msg:
                case Shutdown():
                    break
                # case MidiMessages():
                #     self.synth.add_messages(
                #             msg.last_frame_time,
                #             msg.messages)
