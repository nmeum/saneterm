import sys
import pty
import os
import codecs

import input
from termview import *

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import GLib

WIN_TITLE = "saneterm"
TERM = "dumb"

class PtySource(GLib.Source):
    master = -1

    def __init__(self, cmd):
        GLib.Source.__init__(self)
        self.cmd = cmd

    def prepare(self):
        if self.master != -1:
            return False, -1

        pid, self.master = pty.fork()
        if pid == pty.CHILD:
            # Terminal options enforced by saneterm.
            # Most importantly, local echo is disabled. Instead we show
            # characters on input directly in the GTK termview/TextBuffer.
            os.system("stty -onlcr -echo")

            os.execvpe(self.cmd[0], self.cmd, {"TERM": TERM})

        self.add_unix_fd(self.master, GLib.IOCondition.IN)
        return False, -1

    def check(self):
        return False

    def dispatch(self, callback, args):
        return callback(self.master)

class Terminal(Gtk.Window):
    def __init__(self, cmd):
        Gtk.Window.__init__(self, title=WIN_TITLE)

        self.pty = PtySource(cmd)
        self.pty.set_callback(self.handle_pty)
        self.pty.attach(None)

        self.termview = TermView()
        self.termview.set_wrap_mode(Gtk.WrapMode(Gtk.WrapMode.WORD_CHAR))

        # Block-wise reading from the PTY requires an incremental decoder.
        self.decoder = codecs.getincrementaldecoder('UTF-8')()

        bindings = input.KeyBindings()
        bindings.apply(self.termview)

        self.termview.connect("new-user-input", self.user_input)
        self.add(self.termview)

    def handle_pty(self, master):
        # XXX: Should be possible to read more than one byte here.
        data = os.read(master, 1)
        if not data:
            raise AssertionError("expected data but did not receive any")

        self.termview.insert_data(self.decoder.decode(data))
        return GLib.SOURCE_CONTINUE

    def user_input(self, termview, line):
        os.write(self.pty.master, line.encode("UTF-8"))
