#!/usr/bin/python3

import threading
from typing import Generator, Optional, Self

import jack
import mido

from pyeep.deltalist import DeltaList, Event

# See:
# https://github.com/jackaudio/jackaudio.github.com/wiki/WalkThrough_Dev_LatencyBufferProcess
# https://linuxaudio.github.io/libremusicproduction/html/articles/demystifying-jack-%E2%80%93-beginners-guide-getting-started-jack
# https://github.com/jackaudio/jackaudio.github.com/wiki/WalkThrough_User_jack_control
# https://github.com/jackaudio/jackaudio.github.com/wiki/WalkThrough_Dev_SimpleMidiClient
# https://github.com/jackaudio/jackaudio.github.com/wiki
# http://lalists.stanford.edu/lad/2009/09/0062.html
#
# https://jackaudio.org/api/index.html
# https://jackclient-python.readthedocs.io/en/0.5.4/
# https://jackclient-python.readthedocs.io/en/0.5.4/examples.html
# https://mido.readthedocs.io/en/latest/
# https://mido.readthedocs.io/en/latest/message_types.html
# https://en.wikipedia.org/wiki/General_MIDI
# https://github.com/harryhaaren/JACK-MIDI-Examples


class MidiEvent(Event):
    """
    Frame-timed event carrying a MIDI message
    """
    def __init__(
            self, *,
            msg: Optional[mido.Message] = None,
            data: Optional[bytes] = None,
            **kw):
        super().__init__(**kw)
        self._msg: Optional[mido.Message] = msg
        self._data: Optional[bytes] = data

    @classmethod
    def from_msg(cls, msg: mido.Message, encode: bool = False, **kw) -> Self:
        res = cls(msg=msg, **kw)
        if encode:
            # Trigger encoding
            res.data
        return res

    @classmethod
    def from_data(cls, data: bytes, decode: bool = False, **kw) -> Self:
        res = cls(data=data, **kw)
        if decode:
            # Trigger decoding
            res.msg
        return res

    @property
    def msg(self) -> mido.Message:
        if self._msg is None:
            self._msg = mido.parse([ord(b) for b in self.data])
        return self._msg

    @property
    def data(self) -> bytes:
        if self._data is None:
            self._data = self._msg.bytes()
        return self._data

    def __str__(self):
        return str(self.msg)

    def __repr__(self):
        return f"MidiEvent({self.msg}, +{self.frame_delay})"


class JackComponent:
    def __init__(self, client: jack.Client):
        super().__init__()
        self.client = client
        self.samplerate = self.client.samplerate

    def on_process(self, frames: int):
        raise NotImplementedError(f"{self.__class__.__name__}.on_process not implemented")


class MidiPlayer(JackComponent):
    """
    JACK client that plays a queue of MIDI events
    """
    def __init__(self, client: jack.Client):
        super().__init__(client)
        self.events = DeltaList[MidiEvent]()
        self.events_mutex = threading.Lock()
        self.midi_outport = self.client.midi_outports.register('midi output')

    def play(self, type: str, *, delay_sec: float = 0.0, **args):
        """
        Enqueue a MIDI event to be played
        """
        msg = mido.Message(type, **args)
        evt = MidiEvent.from_msg(msg, encode=True, frame_delay=int(round(delay_sec * self.samplerate)))
        with self.events_mutex:
            self.events.add_event(evt)

    def on_process(self, frames: int):
        self.midi_outport.clear_buffer()

        with self.events_mutex:
            events = self.events.clock_tick(frames)

        for evt in events:
            self.midi_outport.write_midi_event(evt.frame_delay, evt.data)


class MidiReceiver(JackComponent):
    """
    JACK client that receives MIDI events
    """
    def __init__(self, client: jack.Client, inport: jack.OwnMidiPort | None = None):
        super().__init__(client)
        if inport is None:
            self.inport = self.client.midi_inports.register('midi input')
        else:
            self.inport = inport

    def read_events(self) -> Generator[MidiEvent, None, None]:
        frame_time = self.client.last_frame_time
        for offset, indata in self.inport.incoming_midi_events():
            msg = mido.parse([ord(b) for b in indata])
            msg.time = frame_time + offset
            yield msg
