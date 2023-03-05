#!/usr/bin/python3

import contextlib
import threading

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
    def __init__(self, msg: mido.Message, *args, **kw):
        super().__init__(*args, **kw)
        self.msg = msg

    def __str__(self):
        return str(self.msg)

    def __repr__(self):
        return f"MidiEvent({self.msg}, +{self.frame_delay})"


class MidiPlayer(contextlib.ExitStack):
    """
    JACK client that plays a queue of MIDI events
    """
    def __init__(self, name="pyeep MIDI player"):
        super().__init__()
        self.events = DeltaList[MidiEvent]()
        self.events_mutex = threading.Lock()
        self.client = jack.Client(name)
        self.outport = self.client.midi_outports.register('midi output')
        self.client.set_process_callback(self.on_process)
        self.enter_context(self.client)
        self.samplerate = self.client.samplerate

    def play(self, type: str, *, delay_sec: float = 0.0, **args):
        """
        Enqueue a MIDI event to be played
        """
        msg = mido.Message(type, **args)
        evt = MidiEvent(msg, frame_delay=int(round(delay_sec * self.samplerate)))
        with self.events_mutex:
            self.events.add_event(evt)

    def on_process(self, frames: int):
        self.outport.clear_buffer()

        with self.events_mutex:
            events = self.events.clock_tick(frames)

        for evt in events:
            self.outport.write_midi_event(evt.frame_delay, evt.msg.bytes())
