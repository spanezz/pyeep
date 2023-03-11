from __future__ import annotations

from pyeep.jackmidi import MidiPlayer

DRUM_CHANNEL = 9
DRUM_BASS = 36
DRUM_HIGH_TOM = 50
DRUM_LOW_TOM = 45
DRUM_CLOSED_HIHAT = 42
DRUM_CRASH1 = 49
DRUM_SIDE_STICK = 37


class GenerativeScore:
    def __init__(self, *, player: MidiPlayer, bpm: int = 60, **kw):
        self.player = player
        self.bpm = bpm
        self.beat_number: int = 0
        self.channel: int = 0

    def start(self):
        pass

    def pause(self):
        pass

    def stop(self) -> bool:
        return False

    def beat(self):
        self.beat_number += 1

    def drum(self, note: int, position: float, duration: float, velocity: int = 127):
        beat = 60 / self.bpm
        delay = beat * position
        self.player.play("note_on", velocity=velocity, note=note, channel=DRUM_CHANNEL, delay_sec=delay)
        self.player.play("note_off", note=note, channel=DRUM_CHANNEL, delay_sec=delay + beat * duration)

    def note(self, note: int, position: float, duration: float, velocity: int = 127):
        beat = 60 / self.bpm
        delay = beat * position
        self.player.play("note_on", velocity=velocity, note=note, channel=self.channel, delay_sec=delay)
        self.player.play("note_off", note=note, channel=self.channel, delay_sec=delay + beat * duration)

    def bank_program_select(self, bank: int, program: int, position: int = 0):
        # https://www.sweetwater.com/sweetcare/articles/6-what-msb-lsb-refer-for-changing-banks-andprograms/
        # FIXME: I cannot seem to be able to make this work with fluidsynth
        beat = 60 / self.bpm
        delay = beat * position
        self.player.play("control_change", channel=self.channel, control=0, value=bank >> 8, delay_sec=delay)
        self.player.play("control_change", channel=self.channel, control=32, value=bank & 0xff, delay_sec=delay)
        self.player.play("program_change", channel=self.channel, program=program, delay_sec=delay)
