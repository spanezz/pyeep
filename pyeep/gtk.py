from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version('Gdk', '4.0')
gi.require_version("GLib", "2.0")
gi.require_version('Adw', '1')

from gi.repository import Adw, Gdk, GObject, Gio, GLib, Gtk  # noqa
