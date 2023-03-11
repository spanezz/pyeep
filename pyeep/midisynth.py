#!/usr/bin/python3

import math
from collections import deque
from typing import Callable, Type

import mido
import numpy

from . import jackmidi


class Note:
    def __init__(self, note: int, samplerate: int, dtype):
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

    def generate(self, frames: int) -> numpy.ndarray:
        raise NotImplementedError()


class OnOff(Note):
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
            return numpy.full(frames, self.last_attenuation, dtype=self.dtype)

        sample: numpy.ndarray = numpy.zeros(0, dtype=self.dtype)
        for msg in events:
            offset = msg.time - frame_time
            match msg.type:
                case "note_off":
                    if offset > len(sample):
                        sample = numpy.concatenate((sample, numpy.full(offset - len(sample), self.last_attenuation)))
                    self.last_attenuation = 0
                case "note_on":
                    if offset > len(sample):
                        sample = numpy.concatenate((sample, numpy.full(offset - len(sample), self.last_attenuation)))
                    self.last_attenuation = msg.velocity / 127.0

        if frames > len(sample):
            sample = numpy.concatenate((sample, numpy.full(frames - len(sample), self.last_attenuation)))

        return sample


class Sine(Note):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.freq = 440.0 * math.exp2((self.note - 69) / 12)
        self.factor = self.freq * 2.0 * numpy.pi / self.samplerate

    def generate(self, frame_time: int, frames: int) -> numpy.ndarray | None:
        events = self.get_events(frame_time, frames)

        if not events and not self.next_events:
            if self.last_attenuation == 0:
                return None
            # No events: continue from last known value
            x = numpy.arange(frame_time, frame_time + frames)
            return numpy.sin(x * self.factor) * self.last_attenuation

        sample: numpy.ndarray = numpy.zeros(frames, dtype=self.dtype)
        last_offset = 0
        for msg in events:
            offset = msg.time - frame_time
            match msg.type:
                case "note_off":
                    if offset > last_offset:
                        x = numpy.arange(frame_time + last_offset, frame_time + offset)
                        sample[last_offset:offset] = numpy.sin(x * self.factor) * self.last_attenuation
                    self.last_attenuation = 0
                    last_offset = offset
                case "note_on":
                    if offset > last_offset:
                        x = numpy.arange(frame_time + last_offset, frame_time + offset)
                        sample[last_offset:offset] = numpy.sin(x * self.factor) * self.last_attenuation
                    self.last_attenuation = msg.velocity / 127.0
                    last_offset = offset

        if frames > last_offset:
            x = numpy.arange(frame_time + last_offset, frame_time + frames)
            sample[last_offset:frames] = numpy.sin(x * self.factor) * self.last_attenuation

        return sample


class Instrument:
    def __init__(self, note_cls: Type[Note], samplerate: int, dtype):
        self.note_cls = note_cls
        self.samplerate = samplerate
        self.dtype = dtype
        self.notes: dict[int, Note] = {}

    def add_event(self, msg: mido.Message):
        if (note := self.notes.get(msg.note)) is None:
            note = self.note_cls(msg.note, self.samplerate, self.dtype)
            self.notes[msg.note] = note

        note.add_event(msg)

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


class MidiSynth(jackmidi.MidiReceiver):
    """
    Dispatch MIDI events to a software bank of instruments and notes, and
    generate the mixed waveforms
    """
    def __init__(self, name: str, synth_samplerate: int):
        super().__init__(name)
        self.synth_samplerate = synth_samplerate
        self.synth_last_frame_time: int = 0
        self.dtype = numpy.float32
        self.instruments: dict[int, Instrument] = {}
        # Set to a callable to have it invoked at each processing step
        # when midi are processed, with the midi messages that were processed
        self.midi_snoop: Callable[[list[mido.Message]], None] | None = None

    def set_instrument(self, channel: int, note_cls: Type[Note]):
        self.instruments[channel] = Instrument(note_cls, self.synth_samplerate, self.dtype)

    def on_process(self, frames: int):
        """
        JACK processing: enqueue midi events in the right instruments/notes
        """
        midi_processed: list[mido.Message] | None = (
                [] if self.midi_snoop is not None else None)

        self.synth_last_frame_time = int(round(self.client.last_frame_time / self.samplerate * self.synth_samplerate))

        for msg in self.read_events():
            if msg.type not in ("note_on", "note_off"):
                continue
            if (instrument := self.instruments.get(msg.channel)) is None:
                continue
            if midi_processed is not None:
                midi_processed.append(msg)

            # Convert time from self.samplerate to self.synth_samplerate
            msg.time = int(round(msg.time / self.samplerate * self.synth_samplerate))

            instrument.add_event(msg)

        if midi_processed:
            self.midi_snoop(midi_processed)

    def generate(self, frame_time: int, frames: int) -> numpy.ndarray:
        """
        Generate a waveform for the given time
        """
        samples: list[numpy.ndarray] = []
        for instrument in self.instruments.values():
            samples.append(instrument.generate(frame_time, frames))

        if samples:
            return numpy.clip(0, 1, sum(samples))
        else:
            return numpy.zeros(frames, dtype=self.dtype)
