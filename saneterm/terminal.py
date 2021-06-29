import sys
import os
import codecs
import termios
import fcntl
import struct

from . import keys
from . import proc
from . import pty
from .search import SearchBar
from .history import History
from .termview import *

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango

NAME = "saneterm"

class Terminal(Gtk.Window):
    config = {
        'autoscroll': True,
        'wordwrap': True,
    }

    def __init__(self, cmd, limit=-1, vscrollbar=True):
        Gtk.Window.__init__(self, title=NAME)
        self.set_name(NAME)

        self.hist = History()
        self.reset_history_index()

        self.pty = pty.Source(cmd)
        self.pty.set_priority(GLib.PRIORITY_LOW)
        self.pty.set_callback(self.handle_pty)
        self.pty.attach(None)

        self.pty_parser = pty.Parser()

        self.termview = TermView(self.complete, limit)

        # Block-wise reading from the PTY requires an incremental decoder.
        self.decoder = codecs.getincrementaldecoder('UTF-8')()

        self.termview.connect("new-user-input", self.user_input)
        self.termview.connect("termios-ctrlkey", self.termios_ctrl)
        self.termview.connect("size-allocate", self.autoscroll)
        self.termview.connect("populate-popup", self.populate_popup)

        self.connect("configure-event", self.update_size)
        self.connect("destroy", self.destroy)
        self.connect_after("set-focus", self.focus)

        bindings = keys.Bindings(self.termview)
        for key, idx in keys.CTRL.items():
            bindings.add_bind(key, "termios-ctrlkey", idx)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.add(vbox)

        self.search_bar = SearchBar(self.termview)
        vbox.pack_start(self.search_bar, False, True, 0)

        self.scroll = Gtk.ScrolledWindow().new(None, None)
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        self.scroll.add(self.termview)
        self.update_wrapmode()
        vbox.pack_start(self.scroll, True, True, 0)

        if not vscrollbar:
            vscroll = self.scroll.get_vscrollbar()
            vscroll.hide()

        signals = {
            "toggle-search": (),
            "toggle-config": (GObject.TYPE_STRING,),
            "history-entry": (GObject.TYPE_LONG,),
        }

        for name, args in signals.items():
            GObject.signal_new(name, self.termview,
                    GObject.SIGNAL_ACTION, GObject.TYPE_NONE,
                    args)

        self.termview.connect("toggle-search", self.toggle_search, self.search_bar)
        self.termview.connect("toggle-config", self.toggle_config)
        self.termview.connect("history-entry", self.history)

    def complete(self, input):
        # XXX: This could be cached as the CWD shouldn't
        # change unless input is send to the child process.
        cwd = proc.cwd(os.tcgetpgrp(self.pty.master))

        f = completion.FileName(cwd)
        return f.get_matches(input)

    def focus(self, window, widget):
        # If no widget is focused, focus the termview by default.
        # This occurs, for instance, after closing the SearchBar.
        #
        # XXX: Is there a better way to do this?
        if widget is None:
            self.emit("set-focus", self.termview)

    def destroy(self, widget):
        self.hist.close()

    def update_wrapmode(self):
        # XXX: Need to set hscroll mode explicitly and cannot rely on
        # AUTOMATIC, as hypenation may introduce a horizontal scrollbar
        # otherwise. With Gtk+4.0 we can disable hypenation explicitly.
        # See: https://gitlab.gnome.org/GNOME/gtk/-/issues/2384
        if self.config['wordwrap']:
            wmode = Gtk.WrapMode.WORD_CHAR
            hscroll = Gtk.PolicyType.NEVER
        else:
            wmode = Gtk.WrapMode.NONE
            hscroll = Gtk.PolicyType.AUTOMATIC

        self.termview.set_wrap_mode(wmode)

        _, vscroll = self.scroll.get_policy()
        self.scroll.set_policy(hscroll, vscroll)

    def update_size(self, widget, rect):
        # This function allows application running inside the terminal
        # to retrieve the window size using the TIOCGWINSZ ioctl. This
        # is for example used by ls(1) for multi column output. However,
        # since TIOCGWINSZ assumes the terminal be built around a
        # character grid we only provide a heuristic implementation.

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

        decoded = self.decoder.decode(data)

        for (ev, data) in self.pty_parser.parse(decoded):
            if ev is pty.EventType.TEXT:
                self.termview.insert_data(data)
            elif ev is pty.EventType.NEWLINE:
                self.termview.set_replace(False)
                self.termview.insert_data("\n")
            elif ev is pty.EventType.CARRIAGE_RETURN:
                self.termview.goto_line_start()
                self.termview.set_replace(True)
            elif ev is pty.EventType.BELL:
                self.termview.error_bell()
                self.set_urgency_hint(True)
            else:
                raise AssertionError("unknown pty.EventType")

        return GLib.SOURCE_CONTINUE

    def toggle_search(self, termview, search_bar):
        active = search_bar.get_search_mode()
        search_bar.set_search_mode(not active)

    def reset_history_index(self):
        self.hist_index = -1

    def history(self, termview, idx):
        # Backup index and restore it if we hit the beginning of the history
        backup_index = self.hist_index

        self.hist_index += idx
        entry = self.hist.get_entry(self.pty.master, self.hist_index)

        if entry is None:
            if idx > 0:
                # we are going back in time. if there are no older
                # entries, restore history index and bail out.
                self.hist_index = backup_index
                return
            else:
                # we were going forward in time, but no newer entry
                # was found. in this case we just clear the line
                self.reset_history_index()
                entry = ""

        self.termview.emit("kill-after-output")
        self.termview.emit("insert-at-cursor", entry)

    def autoscroll(self, widget, rect):
        if not self.config['autoscroll']:
            return

        # For some reason it is not possible to use .scroll_to_mark()
        # et cetera on the TextView contained in the ScrolledWindow.
        adj = self.scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def toggle_config(self, widget, key):
        self.config[key] = not self.config[key]
        if key == 'wordwrap':
            self.update_wrapmode()

    def populate_popup(self, textview, popup):
        popup.append(Gtk.SeparatorMenuItem())
        for key, enabled in self.config.items():
            mitem = Gtk.CheckMenuItem(key.capitalize())
            mitem.set_active(enabled)

            mitem.connect('toggled', self.toggle_config, key)
            popup.append(mitem)

        popup.show_all()

    def user_input(self, termview, line):
        self.hist.add_entry(self.pty.master, line)
        self.reset_history_index()

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
