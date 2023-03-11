from __future__ import annotations

import argparse
import logging

import gi

from .app import App

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gtk, GLib  # noqa


class LogView(Gtk.ScrolledWindow):
    def __init__(self, max_lines: int = 10):
        super().__init__()
        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_cursor_visible(False)
        self.textview.set_monospace(True)
        self.add(self.textview)
        self.max_lines = max_lines

    def append(self, text: str):
        buffer = self.textview.get_buffer()

        text = text.rstrip()
        if buffer.get_char_count() > 0:
            text = "\n" + text
        buffer.insert(buffer.get_end_iter(), text)

        if (lines := buffer.get_line_count()) > self.max_lines:
            start = buffer.get_start_iter()
            line1 = buffer.get_iter_at_line(lines - self.max_lines)
            buffer.delete(start, line1)


class GtkHandler(logging.Handler):
    def __init__(self, view: LogView, level=logging.NOTSET):
        super().__init__(level)
        self.view = view

    def emit(self, record):
        line = self.format(record)
        self.view.append(line)


class GtkApp(App):
    def __init__(self, args: argparse.Namespace, *, title: str, **kw):
        super().__init__(args, **kw)
        self.window = Gtk.Window(title=title)
        self.window.set_default_size(400, 300)
        self.window.connect("destroy", Gtk.main_quit)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(self.vbox)

        self.logview = LogView()
        self.vbox.pack_end(self.logview, True, True, 0)

    def setup_curses_logging(self):
        FORMAT = "%(levelname)s %(name)s %(message)s"
        formatter = logging.Formatter(FORMAT)
        self.log_handler = GtkHandler(self.logview)
        self.log_handler.setFormatter(formatter)
        # self.log_handler.propagate = False
        logging.getLogger().addHandler(self.log_handler)

    def ui_main(self):
        self.window.show_all()
        self.setup_curses_logging()
        Gtk.main()
        logging.getLogger().removeHandler(self.log_handler)
