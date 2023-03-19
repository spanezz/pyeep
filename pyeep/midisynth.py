from __future__ import annotations

import math
from collections import deque
from typing import Callable, Type

import jack
import mido
import numpy
import scipy.signal

from . import jackmidi


class Note:
    def __init__(self, instrument: "Instrument", note: int, samplerate: int, dtype):
        self.instrument = instrument
        self.note = note
        self.samplerate = samplerate
        self.dtype = dtype
        self.next_events: deque[mido.Message] = deque()
        self.last_attenuation: float = 0

    def add_event(self, msg: mido.Message):
        self.next_events.append(msg)

    def get_events(self, frame_time: int, frames: int) -> list[mido.Message]:
        """
        Dequeue the events we want to process.

        Update last_attenuation if some events need to be skipped
        """
        events: list[mido.Message] = []
        while self.next_events and self.next_events[0].time < frame_time + frames:
            msg = self.next_events.popleft()
            if msg.time < frame_time:
                match msg.type:
                    case "note_on":
                        self.last_attenuation = msg.velocity / 127.0
                    case "note_off":
                        self.last_attenuation = 0
            else:
                events.append(msg)
        return events

    def generate(self, frame_time: int, frames: int) -> numpy.ndarray | None:
        """
        Return `frames` samples at the given frame time.

        If it returns None, it means this note is completely turned off
        """
        events = self.get_events(frame_time, frames)

        if not events and not self.next_events:
            if self.last_attenuation == 0:
                return None
            # No events: continue from last known value
            res = self.synth(frame_time, frames) * self.last_attenuation
            return res

        sample: numpy.ndarray = numpy.zeros(frames, dtype=self.dtype)
        last_offset = 0
        for msg in events:
            offset = msg.time - frame_time
            match msg.type:
                case "note_off":
                    if offset > last_offset:
                        sample[last_offset:offset] = self.synth(
                            frame_time + last_offset, offset - last_offset
                        ) * self.last_attenuation
                    self.last_attenuation = 0
                    last_offset = offset
                case "note_on":
                    if offset > last_offset:
                        sample[last_offset:offset] = self.synth(
                            frame_time + last_offset, offset - last_offset
                        ) * self.last_attenuation
                    self.last_attenuation = msg.velocity / 127.0
                    last_offset = offset

        if frames > last_offset:
            sample[last_offset:frames] = self.synth(
                frame_time + last_offset, frames - last_offset
            ) * self.last_attenuation

        return sample

    def synth(self, frame_time: int, frames: int) -> numpy.ndarray:
        raise NotImplementedError()


class OnOff(Note):
    def synth(self, frame_time: int, frames: int) -> numpy.ndarray:
        return numpy.full(frames, 1, dtype=self.dtype)


class Sine(Note):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.freq = 440.0 * math.exp2((self.note - 69) / 12)
        self.factor = self.freq * 2.0 * numpy.pi / self.samplerate

    def synth(self, frame_time: int, frames: int) -> numpy.ndarray:
        # Use modulus to prevent passing large integer values to numpy.
        # float32 would risk losing the least significant digits
        if self.instrument.transpose:
            note = (self.note - 69) + 2 * self.instrument.transpose / 8192
            freq = 440.0 * math.exp2(note / 12)
            factor = freq * 2.0 * numpy.pi / self.samplerate
        else:
            factor = self.factor
        time = frame_time % self.samplerate
        x = numpy.arange(time, time + frames, dtype=self.dtype)
        return numpy.sin(x * factor, dtype=self.dtype)


class Saw(Note):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.freq = 440.0 * math.exp2((self.note - 69) / 12)
        self.factor = self.freq / self.samplerate

    def synth(self, frame_time: int, frames: int) -> numpy.ndarray:
        if self.instrument.transpose:
            note = (self.note - 69) + 2 * self.instrument.transpose / 8192
            freq = 440.0 * math.exp2(note / 12)
            factor = freq / self.samplerate
        else:
            factor = self.factor
        # Use modulus to prevent passing large integer values to numpy.
        # float32 would risk losing the least significant digits
        time = frame_time % self.samplerate
        x = numpy.arange(time, time + frames, dtype=self.dtype)
        return scipy.signal.sawtooth(2 * numpy.pi * factor * x)


class Instrument:
    def __init__(self, channel: int, note_cls: Type[Note], samplerate: int, dtype):
        self.channel = channel
        self.note_cls = note_cls
        self.samplerate = samplerate
        self.dtype = dtype
        self.notes: dict[int, Note] = {}
        self.transpose: int = 0

    def add_note(self, msg: mido.Message) -> bool:
        if (note := self.notes.get(msg.note)) is None:
            note = self.note_cls(self, msg.note, self.samplerate, self.dtype)
            self.notes[msg.note] = note

        note.add_event(msg)
        return True

    def add_pitchwheel(self, msg: mido.Message):
        # Transpose the notes
        #
        # Pitch is an integer from from -8192 to 8191
        #
        # The GM spec recommends that MIDI devices default to using the
        # entire range of possible Pitch Wheel message values (ie, 0x0000
        # to 0x3FFF) as +/- 2 half steps transposition
        # See http://midi.teragonaudio.com/tech/midispec/wheel.htm
        self.transpose = msg.pitch

    def generate(self, frame_time: int, frames: int) -> numpy.ndarray:
        off: list[int] = []
        samples: list[numpy.ndarray] = []
        for note_id, note in self.notes.items():
            sample = note.generate(frame_time, frames)
            if sample is None:
                off.append(note_id)
            else:
                samples.append(sample)

        for note_id in off:
            del self.notes[note_id]

        if samples:
            return sum(samples)
        else:
            return numpy.zeros(frames, dtype=self.dtype)


class Instruments:
    def __init__(self, in_samplerate: int, out_samplerate: int, dtype):
        self.in_samplerate = in_samplerate
        self.out_samplerate = out_samplerate
        self.out_last_frame_time: int = 0
        self.dtype = dtype
        self.instruments: dict[int, Instrument] = {}

        self.samplerate_conversion: float | None = None
        if self.out_samplerate != self.in_samplerate:
            self.samplerate_conversion = self.out_samplerate / self.in_samplerate

    def set(self, channel: int, note_cls: Type[Note]):
        self.instruments[channel] = Instrument(channel, note_cls, self.out_samplerate, self.dtype)

    def start_input_frame(self, in_last_frame_time: int):
        if self.samplerate_conversion is not None:
            self.out_last_frame_time = int(round(in_last_frame_time * self.samplerate_conversion))
        else:
            self.out_last_frame_time = in_last_frame_time

    def add_event(self, msg: mido.Message) -> bool:
        match msg.type:
            case "note_on" | "note_off":
                if (instrument := self.instruments.get(msg.channel)) is None:
                    return False

                # Convert time from self.in_samplerate to self.out_samplerate
                if self.samplerate_conversion is not None:
                    msg = msg.copy(time=int(round(msg.time * self.samplerate_conversion)))

                return instrument.add_note(msg)

            case "pitchwheel":
                # Convert time from self.in_samplerate to self.out_samplerate
                if self.samplerate_conversion is not None:
                    msg = msg.copy(time=int(round(msg.time * self.samplerate_conversion)))

                for instrument in self.instruments.values():
                    instrument.add_pitchwheel(msg)

                return True
            case _:
                return False

    def generate(self, out_frame_time: int, out_frames: int) -> numpy.ndarray:
        """
        Generate a waveform for the given time, expressed as the output frame
        rate
        """
        samples: list[numpy.ndarray] = []
        for instrument in self.instruments.values():
            samples.append(instrument.generate(out_frame_time, out_frames))

        if samples:
            return numpy.clip(0, 1, sum(samples))
        else:
            return numpy.zeros(out_frames, dtype=self.dtype)


class MidiSynth(jackmidi.MidiReceiver):
    """
    Dispatch MIDI events to a software bank of instruments and notes, and
    generate the mixed waveforms
    """
    def __init__(self, client: jack.Client, *, out_samplerate: int | None = None, **kw):
        super().__init__(client, **kw)
        if out_samplerate is None:
            self.out_samplerate = self.samplerate
        else:
            self.out_samplerate = out_samplerate
        self.dtype = numpy.float32
        self.instruments = Instruments(self.samplerate, self.out_samplerate, self.dtype)

        # Set to a callable to have it invoked at each processing step
        # when midi are processed, with the midi messages that were processed
        self.midi_snoop: Callable[[list[mido.Message]], None] | None = None

    def on_process(self, frames: int):
        """
        JACK processing: enqueue midi events in the right instruments/notes
        """
        midi_processed: list[mido.Message] | None = (
                [] if self.midi_snoop is not None else None)

        self.instruments.start_input_frame(self.client.last_frame_time)

        for msg in self.read_events():
            if self.instruments.add_event(msg):
                if midi_processed is not None:
                    midi_processed.append(msg)

        if midi_processed:
            self.midi_snoop(midi_processed)
