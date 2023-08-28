from __future__ import annotations

import argparse
import logging
import sys

from ..outputs import midisynth
from ..app.aio import AIOApp
from ..app.gtk import GtkApp
from ..app.jack import JackApp
from ..gtk import Gtk
from ..inputs.midi import MidiInput
from ..component.subprocess import BottomComponent

log = logging.getLogger(__name__)


class App(GtkApp, JackApp, AIOApp):
    def __init__(self, args: argparse.Namespace, **kwargs):
        super().__init__(args, **kwargs)
        self.add_component(MidiInput)
        self.add_component(midisynth.Synth)
        if args.controller:
            self.add_component(BottomComponent, path=args.controller)

    def build_main_window(self):
        super().build_main_window()

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.window.set_child(self.grid)

        # TODO: add a MIDI panic button


def main():
    parser = App.argparser(name="midievents", description="MIDI event reader")
    parser.add_argument("--controller", action="store", metavar="socket", help="Controller socket")
    args = parser.parse_args()

    with App(args, title="MIDI Events", application_id="org.enricozini.midievents") as app:
        app.main()


if __name__ == "__main__":
    sys.exit(main())
