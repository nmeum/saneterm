import pty
import os

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

class PtySource(GLib.Source):
    master = -1

    def __init__(self, cmd):
        self.cmd = cmd
        GLib.Source.__init__(self)

    def prepare(self):
        if self.master != -1:
            return False, -1

        pid, self.master = pty.fork()
        if pid == pty.CHILD:
            os.execvpe(self.cmd[0], self.cmd, {"TERM": "dumb"})

        self.add_unix_fd(self.master, GLib.IOCondition.IN)
        return False, -1

    def check(self):
        return False

    def dispatch(self, callback, args):
        return callback(self.master)

class Terminal(Gtk.Window):
    def __init__(self, cmd):
        self.pty = PtySource(cmd)
        self.pty.set_callback(self.handle_pty)
        self.pty.attach(None)

        self.last_mark = None
        Gtk.Window.__init__(self, title="Hello World")

        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode(Gtk.WrapMode.WORD_CHAR))

        self.textbuffer = self.textview.get_buffer()
        self.connect("key-press-event", self.insert)

        self.add(self.textview)

    def handle_pty(self, master):
        data = os.read(master, 1)
        if not data:
            raise AssertionError("expected data but did not receive any")

        end = self.textbuffer.get_end_iter()
        self.textbuffer.insert(end, data.decode('UTF-8'))

        end = self.textbuffer.get_end_iter()
        self.last_mark = self.textbuffer.create_mark(None, end, True)

        return GLib.SOURCE_CONTINUE

    def insert(self, widget, event):
        ch = chr(Gdk.keyval_to_unicode(event.keyval))
        os.write(self.pty.master, ch.encode('UTF-8'))
