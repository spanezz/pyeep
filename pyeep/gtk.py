from __future__ import annotations

import argparse
import functools
import logging
import threading

import gi

import pyeep.gtk

from .app import App, Component, Hub, Message, Shutdown, check_hub

gi.require_version("Gtk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version('Adw', '1')

from gi.repository import Adw, GLib, Gtk, Gio  # noqa


class LogView(Gtk.ScrolledWindow):
    def __init__(self, max_lines: int = 10):
        super().__init__()
        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_cursor_visible(False)
        self.textview.set_monospace(True)
        self.set_child(self.textview)
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


class GtkComponentBox(Component, Gtk.Box):
    HUB = "gtk"

    def __init__(self, *, orientation: Gtk.Orientation = Gtk.Orientation.HORIZONTAL, **kwargs):
        Component.__init__(self, **kwargs)
        Gtk.Box.__init__(self, orientation=orientation)


class GtkComponentWindow(Component, Gtk.Window):
    HUB = "gtk"

    def __init__(self, **kwargs):
        Component.__init__(self, **kwargs)
        Gtk.Window.__init__(self)
        self.connect("close-request", self.on_close)
        self.build()
        self.present()

    def build(self):
        pass

    def on_close(self, win):
        self.hub.remove_component(self)


class GtkHub(Hub):
    HUB = "gtk"

    def __init__(self, gtk_app: Gtk.Application, **kwargs):
        super().__init__(**kwargs)
        self.thread = threading.Thread(name=self.HUB, target=self.run)
        self.gtk_app = gtk_app

    def start(self):
        super().start()
        self.thread.start()

    def join(self):
        super().join()
        self.thread.join()

    def _running_in_hub(self) -> bool:
        return threading.current_thread() == self.thread

    def receive(self, msg: Message):
        if self._running_in_hub():
            self._hub_thread_receive(msg)
        else:
            pyeep.gtk.GLib.idle_add(self._hub_thread_receive, msg)

    @check_hub
    def _hub_thread_receive(self, msg: Message):
        super()._hub_thread_receive(msg)
        if isinstance(msg, Shutdown):
            self.gtk_app.quit()

    def add_component(self, component: Component):
        if self._running_in_hub():
            self._hub_thread_add_component(component)
        else:
            pyeep.gtk.GLib.idle_add(self._hub_thread_add_component, component)

    def remove_component(self, component: Component):
        if self._running_in_hub():
            self._hub_thread_remove_component(component)
        else:
            pyeep.gtk.GLib.idle_add(self._hub_thread_remove_component, component)

    def run(self):
        self.gtk_app.run(None)
        self.send(Shutdown())
        self.app.remove_hub(self)


class GtkApp(App):
    def __init__(
            self,
            args: argparse.Namespace, *,
            application_id: str,
            title: str,
            **kwargs):
        super().__init__(args, **kwargs)
        self.gtk_app = Adw.Application(application_id=application_id)
        self.gtk_app.connect("activate", self.on_activate)

        self.title = title

        self.add_hub(GtkHub, gtk_app=self.gtk_app)

        self.logview = LogView()

    def on_activate(self, gtk_app):
        self.window = Gtk.ApplicationWindow(application=self.gtk_app)
        self.build_main_window()
        self.window.present()

    def build_main_window(self):
        self.window.set_title(self.title)
        self.window.set_default_size(600, 300)

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
