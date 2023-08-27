from __future__ import annotations

import argparse
import logging
import sys

import pyeep.outputs.midisynth
from pyeep.app.aio import AIOApp
from pyeep.app.gtk import GtkApp
from pyeep.app.jack import JackApp
from pyeep.gtk import Gtk

log = logging.getLogger(__name__)


class App(GtkApp, JackApp, AIOApp):
    def __init__(self, args: argparse.Namespace, **kwargs):
        super().__init__(args, **kwargs)
        self.add_component(pyeep.inputs.midi.MidiInput)
        self.add_component(pyeep.outputs.midisynth.Synth)

    def build_main_window(self):
        super().build_main_window()

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.window.set_child(self.grid)

        # TODO: add a MIDI panic button


def main():
    parser = App.argparser(name="midisynth", description="Simple MIDI synthesizer")
    args = parser.parse_args()

    with App(args, title="MIDI Synth", application_id="org.enricozini.midisynth") as app:
        app.main()


if __name__ == "__main__":
    sys.exit(main())
