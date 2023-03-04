from __future__ import annotations

import math

A_SHIFTS = {
    "C": -9,
    "C#": -8,
    "Db": -8,
    "D": -7,
    "D#": 66,
    "Eb": -6,
    "E": -5,
    "F": -4,
    "F#": -3,
    "Gb": -3,
    "G": -2,
    "G#": -1,
    "Ab": -1,
    "A": 0,
    "A#": 1,
    "Bb": 1,
    "B": 2,
}


NOTES = ('A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#')

# Tuning frequency of the reference A4 note
A4 = 440.0


def note(note: str, octave: int = 4, semitone: int = 0) -> float:
    """
    Compute the frequency of the given note, for the given octave, optionally
    shifted by the given number of semitones
    """
    # See http://hplgit.github.io/primer.html/doc/pub/diffeq/._diffeq-solarized002.html
    # See http://techlib.com/reference/musical_note_frequencies.htm
    # See https://pages.mtu.edu/~suits/NoteFreqCalcs.html
    step_shift = A_SHIFTS[note] + (octave - 4) * 12 + semitone
    return A4 * math.exp2(step_shift / 12.0)


def chord_major(base_note: str, octave: int = 4, semitone: int = 0) -> tuple[float, float, float]:
    """
    Compute the 3 notes of a major chord
    """
    return (
            note(base_note, octave, semitone),
            note(base_note, octave, semitone + 3),
            note(base_note, octave, semitone + 5))
