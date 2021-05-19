import sys
import pty
import os
import codecs
import termios

import input
from termview import *

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import GLib

NAME = "saneterm"
TERM = "dumb"

class PtySource(GLib.Source):
    master = -1

    def __init__(self, cmd):
        GLib.Source.__init__(self)
        self.cmd = cmd
        self.tag = None

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

        events = GLib.IOCondition.IN|GLib.IOCondition.HUP
        self.tag = self.add_unix_fd(self.master, events)

        return False, -1

    def check(self):
        return False

    def dispatch(self, callback, args):
        return callback(self, self.tag, self.master)

class Terminal(Gtk.Window):
    def __init__(self, cmd):
        Gtk.Window.__init__(self, title=NAME)
        self.set_name(NAME)

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
        self.termview.connect("interrupt", self.interrupt)

        self.add(self.termview)

    def handle_pty(self, source, tag, master):
        cond = source.query_unix_fd(tag)
        if cond & GLib.IOCondition.HUP:
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE

        # XXX: Should be possible to read more than one byte here.
        data = os.read(master, 1)
        if not data:
            raise AssertionError("expected data but did not receive any")

        self.termview.insert_data(self.decoder.decode(data))
        return GLib.SOURCE_CONTINUE

    def user_input(self, termview, line):
        os.write(self.pty.master, line.encode("UTF-8"))

    def interrupt(self, termview):
        cc = termios.tcgetattr(self.pty.master)[-1]
        os.write(self.pty.master, cc[termios.VINTR])
