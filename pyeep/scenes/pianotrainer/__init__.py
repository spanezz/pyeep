import asyncio
from collections import deque
import enum
import math
from typing import Unpack, override
from statistics import mean

import mido
import numpy as np

from pyeep.models import animation
from pyeep.models.color import Color
from pyeep.models.messages import Message
from pyeep.models.scene import SingleTargetSceneDescription
from pyeep.nodes.scene import SceneArgs
from pyeep.scenes.base import WebSceneSingleTarget
from pyeep.midisynth.messages import MIDIMessages


class Mode(enum.StrEnum):
    """Scene mode."""

    STOP = enum.auto()
    PLAY = enum.auto()
    RECORD = enum.auto()


class Description(SingleTargetSceneDescription):
    """Heartbeat scene description."""


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_str(midinote: int) -> str:
    """Stringify the value of a MIDI note."""
    octave = midinote // 12
    note = midinote % 12
    return f"{NOTE_NAMES[note]}{octave}"


@Description.scene
class PianoTrainer(WebSceneSingleTarget[Description]):
    """Pulse lights in sync with heartbeat."""

    def __init__(self, **kwargs: Unpack[SceneArgs[Description]]) -> None:
        super().__init__(**kwargs)
        #: Sequence of expected notes
        self.sequence: list[int] = []
        #: Sequence index of the next expected note
        self.next_note: int = 0
        #: Last note time
        self.last_note_time: float | None = None
        #: Last play speeds used to keep a running average
        self.play_speeds: deque[float] = deque(maxlen=3)
        #: Speed between notes considered to speed
        self.top_speed: float = 0.02
        #: Minimum number of leading good notes that cause score attenuation
        self.lead_good_notes: int = 50
        #: Number of good notes accrued in the play session
        self.count_good: int = 0
        #: MIDI input sample rate, used to convert frame times to seconds
        self.sample_rate: int = 0
        #: Current scene mode
        self.mode: Mode = Mode.STOP

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case MIDIMessages():
                if not self.active:
                    return
                for raw in msg.messages:
                    midimsg = mido.Message.from_bytes(
                        raw.message, time=raw.frame_time / msg.sample_rate
                    )
                    await self.on_midi(midimsg)
            case _:
                await super().receive(msg)

    async def start_mode_record(self) -> None:
        self.log.info("Recording a sequence. Press stop or play when done.")
        self.mode = Mode.RECORD
        self.sequence = []

    async def start_mode_play(self) -> None:
        if self.sequence:
            self.log.info(
                "Play started with sequence: %s",
                " ".join(note_str(note) for note in self.sequence),
            )
            self.mode = Mode.PLAY
            self.next_note = 0
            self.last_note_time = None
            self.count_good = 0
            await self.set_color(
                animation.ColorPulse(
                    color=Color(red=0, green=0, blue=1),
                    duration_ns=100_000_000,
                )
            )
            await self.set_power(0)
        else:
            self.log.warning("No sequence recorded: record one to play")
            self.mode = Mode.STOP

    async def start_mode_stop(self) -> None:
        match self.mode:
            case Mode.RECORD:
                self.log.info(
                    "Sequence recorded: %s",
                    " ".join(note_str(note) for note in self.sequence),
                )
            case Mode.PLAY:
                self.log.info(
                    "Playing stopped after %d good notes.", self.count_good
                )
        self.mode = Mode.STOP

    async def on_note_on(self, note: int, note_time: float) -> None:
        # self.log.info("Note on: %s", note_str(note))
        match self.mode:
            case Mode.RECORD:
                self.sequence.append(note)
            case Mode.PLAY:
                expected = self.sequence[self.next_note]
                if note == expected:
                    self.next_note = (self.next_note + 1) % len(self.sequence)
                    await self.on_good_note(note_time)
                else:
                    await self.on_bad_note()
            case Mode.STOP:
                if self.sequence:
                    self.log.info("Press play to start")
                else:
                    self.log.info("Press record to record a sequence")

    async def on_good_note(self, note_time: float) -> None:
        self.count_good += 1
        if self.last_note_time is not None:
            self.play_speeds.append(note_time - self.last_note_time)
        self.last_note_time = note_time

        if len(self.play_speeds) < 3:
            self.log.info("good, keep playing...")
        else:
            speed_score = self.top_speed / mean(self.play_speeds)
            lead_attenuation = math.log(self.count_good, self.lead_good_notes)
            score = speed_score * lead_attenuation
            self.log.info(
                "good. Score: %.2f (speed: %.2f, duration: %.2f)",
                score,
                speed_score,
                lead_attenuation,
            )
            await self.on_score(score)

    async def on_bad_note(self) -> None:
        self.log.warning("Bad note!")
        await self.set_color(
            animation.ColorPulse(
                color=Color(red=1, green=0, blue=0),
                duration_ns=500_000_000,
            )
        )
        await self.set_power(0)
        await self.start_mode_stop()

    async def set_top_speed(self, value: float) -> None:
        self.log.info("Top speed set to %.2f", value)
        self.top_speed = value

    async def set_lead_good_notes(self, value: int) -> None:
        self.log.info("Lead good notes %d", value)
        self.lead_good_notes = value

    async def on_score(self, score: float) -> None:
        """Notify a new score."""
        value = np.clip(score, 0, 1)
        extra_value = np.clip(score - value, 0, 1)
        await self.set_color(
            color=Color(red=extra_value, green=value, blue=extra_value)
        )
        await self.set_power(power=value)

    async def on_midi(self, msg: mido.Message) -> None:
        match msg.type:
            case "note_on":
                # self.log.info("MIDI note %s on: %s", note_str(msg.note), msg)
                await self.on_note_on(msg.note, msg.time)
            case "note_off":
                # self.log.info("MIDI note %s off: %s", note_str(msg.note), msg)
                pass
            case "control_change":
                match msg.control:
                    case 21:
                        # First pot
                        await self.set_top_speed(0.5 * msg.value / 127)
                    case 22:  # | 23 | 24 | 25 | 26 | 27 | 28:
                        # Second pot
                        await self.set_lead_good_notes(msg.value + 1)
                        # self.log.info(
                        #     "MIDI pot %d: %.2f", msg.control, msg.value / 127
                        # )
                    case 115:
                        if msg.value == 0:
                            await self.start_mode_play()
                    case 116:
                        if msg.value == 127:
                            await self.start_mode_stop()
                    case 117:
                        if msg.value == 0:
                            await self.start_mode_record()
                    case _:
                        self.log.info("MIDI unhandled control change: %s", msg)

            case _:
                self.log.info("MIDI unhandled: %s", msg)
