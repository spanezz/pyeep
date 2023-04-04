from __future__ import annotations

import argparse
import logging
import threading

import gi

import pyeep.gtk

from .app import App, Component, Hub, Message, Shutdown

gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")

from gi.repository import GLib, Gtk  # noqa


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


class GtkLoggingHandler(logging.Handler):
    def __init__(self, view: LogView, level=logging.NOTSET):
        super().__init__(level)
        self.view = view

    def emit(self, record):
        line = self.format(record)
        pyeep.gtk.GLib.idle_add(self.view.append, line)


class GtkComponent(Component):
    HUB = "gtk"


class GtkHub(Hub):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "gtk")
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.name, target=self.run)

    def start(self):
        super().start()
        self.thread.start()

    def join(self):
        super().join()
        self.thread.join()

    def receive(self, msg: Message):
        pyeep.gtk.GLib.idle_add(self._hub_thread_receive, msg)

    def _hub_thread_receive(self, msg: Message):
        super()._hub_thread_receive(msg)
        if msg.name == "shutdown":
            Gtk.main_quit()

    def add_component(self, component: Component):
        pyeep.gtk.GLib.idle_add(self._hub_thread_add_component, component)

    def run(self):
        Gtk.main()
        self.app.remove_hub(self)


class GtkApp(App):
    def __init__(self, args: argparse.Namespace, *, title: str, **kw):
        super().__init__(args, **kw)
        self.add_hub(GtkHub)

        self.window = Gtk.Window(title=title)
        self.window.set_default_size(400, 300)
        self.window.connect("destroy", self._destroy)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(self.vbox)

        self.logview = LogView()
        self.vbox.pack_end(self.logview, True, True, 0)

    def _destroy(self, win):
        self.send(Shutdown())
        Gtk.main_quit()

    def setup_logging(self):
        super().setup_logging()
        pyeep.gtk.GLib.idle_add(self._setup_gtk_logging)

    def _setup_gtk_logging(self):
        FORMAT = "%(levelname)s %(name)s %(message)s"
        formatter = logging.Formatter(FORMAT)
        log_handler = GtkLoggingHandler(self.logview)
        log_handler.setFormatter(formatter)
        # self.log_handler.propagate = False
        logging.getLogger().addHandler(log_handler)

    def main_init(self):
        super().main_init()
        self.window.show_all()
