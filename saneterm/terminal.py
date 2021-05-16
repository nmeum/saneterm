import sys
import pty
import os
import codecs

import input

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject

WIN_TITLE = "saneterm"
TERM = "dumb"

# XXX: Can also be looked up using unicodedata.lookup("DEL").
DEL_CHAR = b'\x7f'

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
            # characters on input directly in the GTK TextView/TextBuffer.
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

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode(Gtk.WrapMode.WORD_CHAR))

        self.textbuffer = self.textview.get_buffer()
        self.textbuffer.connect("end-user-action", self.user_input)

        end = self.textbuffer.get_end_iter()
        self.last_mark = self.textbuffer.create_mark(None, end, True)
        self.last_output_mark = None

        # Block-wise reading from the PTY requires an incremental decoder.
        self.decoder = codecs.getincrementaldecoder('UTF-8')()

        bindings = input.KeyBindings()
        bindings.apply(self.textview)

        self.bind_custom_signals()
        self.add(self.textview)

    def bind_custom_signals(self):
        signals = {
            "kill-after-output": self.kill_after_output,
            "move-input-start": self.move_input_start,
            "move-input-end": self.move_input_end,
        }

        for signal in signals.items():
            name, func = signal
            GObject.signal_new(name, self.textview,
                    GObject.SIGNAL_ACTION, GObject.TYPE_NONE,
                    ())

            self.textview.connect(name, func)

    def handle_pty(self, master):
        # XXX: Should be possible to read more than one byte here.
        data = os.read(master, 1)
        if not data:
            raise AssertionError("expected data but did not receive any")

        end = self.textbuffer.get_end_iter()
        self.textbuffer.insert(end, self.decoder.decode(data))

        end = self.textbuffer.get_end_iter()
        self.last_mark = self.textbuffer.create_mark(None, end, True)
        self.last_output_mark = self.last_mark

        return GLib.SOURCE_CONTINUE

    def user_input(self, buffer):
        start = buffer.get_iter_at_mark(self.last_mark)
        end = buffer.get_end_iter()

        text = buffer.get_text(start, end, True)
        if text == "\n":
            start = buffer.get_iter_at_mark(self.last_output_mark)
            line = buffer.get_text(start, end, True)

            os.write(self.pty.master, line.encode("UTF-8"))
            self.last_output_mark = buffer.create_mark(None, end, True)

        self.last_mark = buffer.create_mark(None, end, True)

    def kill_after_output(self, textview):
        if self.last_output_mark is None:
            return
        buffer = textview.get_buffer()

        start = buffer.get_iter_at_mark(self.last_output_mark)
        end = buffer.get_end_iter()

        buffer.delete(start, end)

    def move_input_start(self, textview):
        if self.last_output_mark is None:
            return
        buffer = textview.get_buffer()

        start = buffer.get_iter_at_mark(self.last_output_mark)
        buffer.place_cursor(start)

    def move_input_end(self, textview):
        buffer = textview.get_buffer()

        end = buffer.get_iter_at_mark(self.last_mark)
        buffer.place_cursor(end)
