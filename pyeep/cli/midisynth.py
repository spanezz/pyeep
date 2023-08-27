from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from ..outputs import midisynth
from ..app.aio import AIOApp
from ..app.gtk import GtkApp
from ..app.jack import JackApp
from ..component.aio import AIOComponent
from ..gtk import Gtk
from ..messages.component import Shutdown
from ..messages.jsonable import Jsonable
from ..inputs.midi import MidiInput

log = logging.getLogger(__name__)


class ControllerComponent(AIOComponent):
    """
    Component that interfaces with a controller program
    """
    def __init__(self, path: Path, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.read_messages_task: asyncio.Task | None = None
        self.returncode: int | None = None
        self.workdir: Path | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def _read_messages(self):
        try:
            while (line := await self.reader.readline()):
                jsonable = json.loads(line)
                cls = Jsonable.jsonable_class(jsonable)
                if cls is None:
                    continue

                jsonable["src"] = self

                try:
                    msg = cls(**jsonable)
                except Exception as e:
                    self.logger.error("cannot instantiate message: %s", e)
                    continue

                print("RECEIVED", msg)
                self.send(msg)
        finally:
            self.receive(Shutdown())

    async def run(self):
        self.reader, self.writer = await asyncio.open_unix_connection(path=self.path)
        self.read_messages_task = asyncio.create_task(self._read_messages())

        while True:
            match (msg := await self.next_message()):
                case Shutdown():
                    if self.proc is not None:
                        await self._terminate_process()
                    break
                case _:
                    if msg.src != self:
                        print("SEND", msg)
                        line = json.dumps(msg.as_jsonable()) + "\n"
                        self.writer.write(line.encode())
                        await self.writer.drain()


class App(GtkApp, JackApp, AIOApp):
    def __init__(self, args: argparse.Namespace, **kwargs):
        super().__init__(args, **kwargs)
        self.add_component(MidiInput)
        self.add_component(midisynth.Synth)
        if args.controller:
            self.add_component(ControllerComponent, path=args.controller)

    def build_main_window(self):
        super().build_main_window()

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.window.set_child(self.grid)

        # TODO: add a MIDI panic button


def main():
    parser = App.argparser(name="midisynth", description="Simple MIDI synthesizer")
    parser.add_argument("--controller", action="store", metavar="socket", help="Controller socket")
    args = parser.parse_args()

    with App(args, title="MIDI Synth", application_id="org.enricozini.midisynth") as app:
        app.main()


if __name__ == "__main__":
    sys.exit(main())
