from __future__ import annotations

import argparse
import functools
import logging
import threading
from typing import Callable, Generic, TypeVar

import gi

from .app import App, Component, Hub, Message, Shutdown, check_hub

gi.require_version("Gtk", "4.0")
gi.require_version('Gdk', '4.0')
gi.require_version("GLib", "2.0")
gi.require_version('Adw', '1')

from gi.repository import Adw, GLib, Gtk, Gio, Gdk  # noqa


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


class GtkComponent(Component):
    HUB = "gtk"

    def __init__(self, *, hub: "GtkHub", **kwargs):
        super().__init__(hub=hub, **kwargs)
        self.hub: "GtkHub"

    @functools.cached_property
    def widget(self) -> Gtk.Widget:
        """
        Return the widget to control this component
        """
        return self.build()

    def build(self) -> Gtk.Widget:
        """
        Build the widget to control this component
        """
        raise NotImplementedError(f"{self.__class__.__name__}.build not implemented")


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


C = TypeVar("C", bound=Component)


class ControllerWidget(Gtk.Frame):
    def __init__(self, *, label: str):
        super().__init__(label=label)

        self.set_margin_bottom(10)
        self.grid = Gtk.Grid()
        self.set_child(self.grid)


class Controller(Generic[C], GtkComponent):
    Widget: ControllerWidget = ControllerWidget

    def __init__(self, *, component: C, **kwargs):
        super().__init__(**kwargs)
        self.component = component

    def build(self) -> ControllerWidget:
        return self.Widget(label=self.component.description)


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
