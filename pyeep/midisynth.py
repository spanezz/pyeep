#!/usr/bin/python3

from collections import deque
from typing import Callable, Type

import mido
import numpy
import scipy.signal

from . import jackmidi

# from resampy.core import resample


class Note:
    def __init__(self, note: int, dtype):
        self.note = note
        self.dtype = dtype
        self.next_events: deque[jackmidi.MidiEventAbsolute] = deque()

    def add_event(self, evt: jackmidi.MidiEventAbsolute):
        self.next_events.append(evt)

    def generate(self, frames: int) -> numpy.ndarray:
        raise NotImplementedError()


class OnOff(Note):
    def __init__(self, note: int, dtype):
        super().__init__(note, dtype)
        self.last_value: float = 0

    def generate(self, frame_time: int, frames: int) -> numpy.ndarray | None:
        """
        Return `frames` samples at the given frame time.

        If it returns None, it means this note is completely turned off
        """
        # Dequeue the events we want to process
        events: list[jackmidi.MidiEventAbsolute] = []
        while self.next_events and self.next_events[0].frame_time < frame_time + frames:
            evt = self.next_events.popleft()
            if evt.frame_time < frame_time:
                match evt.msg.type:
                    case "note_on":
                        self.last_value = evt.msg.velocity / 127.0
                    case "note_off":
                        self.last_value = 0
            else:
                events.append(evt)

        if not events and not self.next_events:
            if self.last_value == 0:
                return None
            # No events: continue from last known value
            return numpy.full(frames, self.last_value, dtype=self.dtype)

        sample: numpy.ndarray = numpy.zeros(0, dtype=self.dtype)
        for evt in events:
            offset = evt.frame_time - frame_time
            match evt.msg.type:
                case "note_off":
                    if offset > len(sample):
                        sample = numpy.concatenate((sample, numpy.full(offset - len(sample), self.last_value)))
                    self.last_value = 0
                case "note_on":
                    if offset > len(sample):
                        sample = numpy.concatenate((sample, numpy.full(offset - len(sample), self.last_value)))
                    self.last_value = evt.msg.velocity / 127.0

        if frames > len(sample):
            sample = numpy.concatenate((sample, numpy.full(frames - len(sample), self.last_value)))

        return sample


class Instrument:
    def __init__(self, note_cls: Type[Note], dtype):
        self.note_cls = note_cls
        self.dtype = dtype
        self.notes: dict[int, Note] = {}

    def add_event(self, evt: jackmidi.MidiEventAbsolute):
        if (note := self.notes.get(evt.msg.note)) is None:
            note = self.note_cls(evt.msg.note, self.dtype)
            self.notes[evt.msg.note] = note

        note.add_event(evt)

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dtype = numpy.float32
        self.instruments: dict[int, Instrument] = {
            0: Instrument(OnOff, self.dtype),
        }
        # Set to a callable to have it invoked at each processing step
        # when midi are processed, with the midi messages that were processed
        self.midi_snoop: Callable[[list[mido.Message]], None] | None = None

    def on_process(self, frames: int):
        """
        JACK processing: enqueue midi events in the right instruments/notes
        """
        midi_processed: list[mido.Message] | None = (
                [] if self.midi_snoop is not None else None)

        for evt in self.read_events():
            if evt.msg.type not in ("note_on", "note_off"):
                continue
            if (instrument := self.instruments.get(evt.msg.channel)) is None:
                continue
            if midi_processed is not None:
                midi_processed.append(evt.msg)
            instrument.add_event(evt)

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

    def generate_resampled(self, frame_time: int, frames: int, out_sample_rate: int) -> numpy.ndarray:
        """
        Generate a waveform for the given time, resampled to the given frame rate
        """
        orig = self.generate(frame_time, frames)
        # return numpy.clip(0, 1, resample(orig, self.samplerate, out_sample_rate))
        return numpy.clip(0, 1, scipy.signal.resample(orig, round(frames / self.samplerate * out_sample_rate)))
