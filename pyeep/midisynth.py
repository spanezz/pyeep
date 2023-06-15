from __future__ import annotations

import math
import threading
from collections import deque
from typing import NamedTuple, Sequence, Type

import mido
import numpy
import scipy.signal


class AudioConfig(NamedTuple):
    in_samplerate: int
    out_samplerate: int
    dtype: type


class Note:
    def __init__(self, instrument: "Instrument", note: int):
        self.audio_config = instrument.audio_config
        self.note = note
        self.next_events: deque[mido.Message] = deque()
        self.last_note: mido.Message | None = None
        self.last_pitchwheel: mido.Message | None = None

    def get_semitone(self) -> float:
        if (msg := self.last_pitchwheel) is not None and (t := msg.pitch):
            return (self.note - 69) + 2 * t / 8192
        else:
            return self.note - 69

    def get_freq(self) -> float:
        return 440.0 * math.exp2(self.get_semitone() / 12)

    def add_event(self, msg: mido.Message):
        self.next_events.append(msg)

    def _process_event(self, msg: mido.Message):
        match msg.type:
            case "note_on":
                self.last_note = msg
            case "note_off":
                self.last_note = None
            case "pitchwheel":
                if msg.pitch == 0:
                    self.last_pitchwheel = None
                else:
                    self.last_pitchwheel = msg

    def get_events(self, frame_time: int, frames: int) -> list[mido.Message]:
        """
        Dequeue the events we want to process.

        If some events need to be skipped, keep track of the last one
        """
        events: list[mido.Message] = []
        while self.next_events and self.next_events[0].time < frame_time + frames:
            msg = self.next_events.popleft()
            if msg.time < frame_time:
                self._process_event(msg)
            else:
                events.append(msg)
        return events

    def add_wave(self, frame_time: int, array: numpy.ndarray, envelope: numpy.ndarray):
        raise NotImplementedError()

    def get_envelope(self, frame_time: int, frames: int) -> numpy.ndarray:
        if self.last_note is None:
            return numpy.zeros(frames, dtype=self.audio_config.dtype)
        return numpy.full(frames, self.last_note.velocity / 127, dtype=self.audio_config.dtype)

    def synth(self, frame_time: int, array: numpy.ndarray) -> None:
        frames = len(array)
        envelope = self.get_envelope(frame_time, frames)
        self.add_wave(frame_time, array, envelope)

    def generate(self, frame_time: int, array: numpy.ndarray) -> bool:
        """
        Generate samples and add them to the values in the array, effectively
        mixing the output of this note into the array.

        Return False if this note is completely turned off, True if it will
        generate more samples in the future
        """
        frames = len(array)
        events = self.get_events(frame_time, frames)

        if not events and not self.next_events:
            if self.last_note is None:
                return False
            # No events: continue from last known value
            self.synth(frame_time, array)
            return True

        last_offset = 0
        for msg in events:
            offset = msg.time - frame_time
            if offset > last_offset:
                self.synth(frame_time + last_offset, array[last_offset:offset])
            self._process_event(msg)
            last_offset = offset

        if frames > last_offset:
            self.synth(frame_time + last_offset, array[last_offset:frames])

        return True


class Sine(Note):
    def add_wave(self, frame_time: int, array: numpy.ndarray, envelope: numpy.ndarray) -> None:
        if self.last_note is None:
            return
        dtype = self.audio_config.dtype
        rate = self.audio_config.out_samplerate
        # Use modulus to prevent passing large integer values to numpy.
        # float32 would risk losing the least significant digits
        factor = self.get_freq() * 2.0 * numpy.pi / rate
        time = frame_time % rate
        x = numpy.arange(time, time + len(array), dtype=dtype)
        array += numpy.sin(x * factor, dtype=dtype) * envelope


class Saw(Note):
    def add_wave(self, frame_time: int, array: numpy.ndarray, envelope: numpy.ndarray) -> None:
        if self.last_note is None:
            return
        dtype = self.audio_config.dtype
        rate = self.audio_config.out_samplerate
        factor = self.get_freq() / rate
        # Use modulus to prevent passing large integer values to numpy.
        # float32 would risk losing the least significant digits
        time = frame_time % rate
        x = numpy.arange(time, time + len(array), dtype=dtype)
        array += scipy.signal.sawtooth(2 * numpy.pi * factor * x) * envelope


class Instrument:
    def __init__(self, audio_config: AudioConfig, channel: int, note_cls: Type[Note]):
        self.audio_config = audio_config
        self.channel = channel
        self.note_cls = note_cls
        self.notes: dict[int, Note] = {}

    def add_note(self, msg: mido.Message) -> bool:
        if (note := self.notes.get(msg.note)) is None:
            note = self.note_cls(self, msg.note)
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
        for note in self.notes.values():
            note.add_event(msg)

    def generate(self, frame_time: int, array: numpy.ndarray) -> numpy.ndarray:
        for note_id, note in list(self.notes.items()):
            if not note.generate(frame_time, array):
                del self.notes[note_id]


class Instruments:
    """
    One instrument bank, mapping channel numbers to Instrument instances
    """
    def __init__(self, audio_config: AudioConfig):
        self.audio_config = audio_config
        self.out_last_frame_time: int = 0
        self.instruments: dict[int, Instrument] = {}

        self.samplerate_conversion: float | None = None
        if self.audio_config.out_samplerate != self.audio_config.in_samplerate:
            self.samplerate_conversion = self.audio_config.out_samplerate / self.audio_config.in_samplerate

    def set(self, channel: int, note_cls: Type[Note]):
        self.instruments[channel] = Instrument(self.audio_config, channel, note_cls)

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

    def generate(self, out_frame_time: int, array: numpy.ndarray) -> numpy.ndarray:
        """
        Generate a waveform for the given time, expressed as the output frame
        rate
        """
        array[:] = 0
        for instrument in self.instruments.values():
            instrument.generate(out_frame_time, array)


class MidiSynth:
    """
    Dispatch MIDI events to a software bank of instruments and notes, and
    generate the mixed waveforms
    """
    def __init__(self, *, in_samplerate: int):
        self.in_samplerate = in_samplerate
        self.instrument_banks: list[Instruments] = []
        self.instrument_banks_lock = threading.Lock()

    def add_output(self, instruments: Instruments) -> None:
        """
        Create a new output synthesizer
        """
        if instruments.audio_config.in_samplerate != self.in_samplerate:
            raise RuntimeError(
                    "Audio config in_samplerate mismatch:"
                    f" ours is {self.audio_config.in_samplerate},"
                    f" new instruments is {instruments.audio_config.in_samplerate}")
        with self.instrument_banks_lock:
            self.instrument_banks.append(instruments)

    def add_messages(self, last_frame_time: int, messages: Sequence[mido.Message]):
        """
        Enqueue midi events in the right instruments/notes
        """
        with self.instrument_banks_lock:
            for instruments in self.instrument_banks:
                instruments.start_input_frame(last_frame_time)

            for msg in messages:
                for i in self.instrument_banks:
                    i.add_event(msg)
