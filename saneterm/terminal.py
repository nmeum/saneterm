import sys
import pty
import os
import codecs
import termios
import fcntl
import struct

import keys
from termview import *

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

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

            os.environ["TERM"] = TERM
            os.execvp(self.cmd[0], self.cmd)

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

        self.termview.connect("new-user-input", self.user_input)
        self.termview.connect("termios-ctrlkey", self.termios_ctrl)
        self.connect("size-allocate", self.update_size)

        bindings = keys.Bindings(self.termview)
        for key, idx in keys.CTRL.items():
            bindings.add_bind(key, "termios-ctrlkey", idx)

        scroll = Gtk.ScrolledWindow().new(None, None)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)

        scroll.add(self.termview)
        self.add(scroll)

    def update_size(self, widget, rect):
        # PTY must already be initialized
        if self.pty.master == -1:
            return

        # Widget width/height in pixels, is later converted
        # to rows/columns by dividing these values by the
        # font width/height as determined by the PangoLayout.
        width, height = widget.get_size()

        ctx = self.termview.get_pango_context()
        layout = Pango.Layout(ctx)
        layout.set_markup(" ") # assumes monospace
        fw, fh = layout.get_pixel_size()

        rows = int(height / fh)
        cols = int(width / fw)

        # TODO: use tcsetwinsize() instead of the ioctl.
        # See: https://github.com/python/cpython/pull/23686
        ws = struct.pack('HHHH', rows, cols, width, height) # struct winsize
        fcntl.ioctl(self.pty.master, termios.TIOCSWINSZ, ws)

    def handle_pty(self, source, tag, master):
        cond = source.query_unix_fd(tag)
        if cond & GLib.IOCondition.HUP:
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE

        data = os.read(master, 4096)
        if not data:
            raise AssertionError("expected data but did not receive any")

        self.termview.insert_data(self.decoder.decode(data))
        return GLib.SOURCE_CONTINUE

    def user_input(self, termview, line):
        os.write(self.pty.master, line.encode("UTF-8"))

    def termios_ctrl(self, termview, cidx):
        # termios ctrl keys are ignored if the cursor is not at the
        # buffer position where the next character would appear.
        if not termview.cursor_at_end():
            return
        elif cidx == termios.VEOF:
            termview.flush()

        # TODO: Employ some heuristic to cache tcgetattr result.
        cc = termios.tcgetattr(self.pty.master)[-1]
        os.write(self.pty.master, cc[cidx])

        # XXX: Clear line-based buffer here (i.e. update the
        # marks in TermView) in case the application doesn't
        # write anything to the PTY on receiving the CC.
