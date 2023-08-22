from __future__ import annotations

import argparse
import logging
import threading
from typing import Callable

from . import App, Hub
from ..component.base import check_hub
from ..messages.message import Message
from ..messages.component import Shutdown

from ..gtk import Adw, GLib, Gtk


class LogView(Gtk.ScrolledWindow):
    def __init__(self, max_lines: int = 500):
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
            found, line1 = buffer.get_iter_at_line(lines - self.max_lines)
            buffer.delete(start, line1)

        if (lines := buffer.get_line_count()) > 0:
            found, line1 = buffer.get_iter_at_line(lines - 1)
            mark = buffer.create_mark(None, line1, False)
            self.textview.scroll_mark_onscreen(mark)


class GtkLoggingHandler(logging.Handler):
    def __init__(self, view: LogView, level=logging.NOTSET):
        super().__init__(level)
        self.view = view

    def emit(self, record):
        line = self.format(record)
        GLib.idle_add(self.view.append, line)


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

    def run_in_hub(self, f: Callable, *args, **kwargs):
        if self._running_in_hub():
            f(*args, **kwargs)
        else:
            GLib.idle_add(f, *args, **kwargs)

    @check_hub
    def _hub_thread_receive(self, msg: Message):
        super()._hub_thread_receive(msg)
        if isinstance(msg, Shutdown):
            self.gtk_app.quit()

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
            gui_logging: bool = False,
            **kwargs):
        super().__init__(args, **kwargs)
        self.gtk_app = Adw.Application(application_id=application_id)
        self.gtk_app.connect("activate", self.on_activate)

        self.title = title

        self.add_hub(GtkHub, gtk_app=self.gtk_app)

        self.logview: LogView | None = None
        if gui_logging:
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
        if self.logview:
            GLib.idle_add(self._setup_gtk_logging)

    def _setup_gtk_logging(self):
        FORMAT = "%(levelname)s %(name)s %(message)s"
        formatter = logging.Formatter(FORMAT)
        log_handler = GtkLoggingHandler(self.logview)
        log_handler.setFormatter(formatter)
        # self.log_handler.propagate = False
        logging.getLogger().addHandler(log_handler)
