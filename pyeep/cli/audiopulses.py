from __future__ import annotations

import argparse
import logging
import sys

from ..app.aio import AIOApp
from ..app.gtk import GtkApp
from ..app.jack import JackApp
from ..gtk import Gtk
from ..outputs.audiopulses import Pulses
from ..component.subprocess import BottomComponent

log = logging.getLogger(__name__)


class App(GtkApp, JackApp, AIOApp):
    def __init__(self, args: argparse.Namespace, **kwargs):
        super().__init__(args, **kwargs)
        self.add_component(Pulses)
        if args.controller:
            self.add_component(BottomComponent, path=args.controller)

    def build_main_window(self):
        super().build_main_window()

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.window.set_child(self.grid)


def main():
    parser = App.argparser(name="audiopulses", description="Audio pulses generator")
    parser.add_argument("--controller", action="store", metavar="socket", help="Controller socket")
    args = parser.parse_args()

    with App(args, title="Audio Pulses", application_id="org.enricozini.audiopulses") as app:
        app.main()


if __name__ == "__main__":
    sys.exit(main())
