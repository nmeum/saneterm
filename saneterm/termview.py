from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from . import completion

class TermBuffer(Gtk.TextBuffer):
    """
    Buffer which stores a limit amount of lines. If the limit is -1
    an unlimited amount of lines is stored. Old lines are deleted
    automatically if the limit is exceeded. Furthermore, the buffer
    provides some facilities for more native copy/paste handling.
    """

    def __init__(self, limit):
        Gtk.TextBuffer.__init__(self)
        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)

        if limit == -1:
            return # unlimited

        self.limit = limit
        self.connect_after("insert-text", self.__insert_text)

    def do_mark_set(self, loc, mark):
        # Gtk only partially adheres to the freedesktop.org clipboard
        # specification. If text is selected, this text is copied to the
        # primary clipboard. However, if the user unselects the text by
        # clicking somewhere else the clipboard is cleared. This has
        # been a known bug in Gtk for over 12 years. The code here is a
        # dirty workaround for this bug.
        #
        # See https://gitlab.gnome.org/GNOME/gtk/-/issues/317

        selection = self.get_selection_bounds()
        if selection:
            start, end = selection
            text = self.get_text(start, end, True)
            self._clipboard.set_text(text, -1)
        else:
            Gtk.TextBuffer.do_mark_set(self, loc, mark)

    def __insert_text(self, buffer, loc, text, len):
        lines = buffer.get_line_count()
        diff = lines - self.limit
        if diff <= 0:
            return

        end = buffer.get_start_iter()
        end.forward_lines(diff)

        start = buffer.get_start_iter()
        buffer.delete(start, end)

        # Revalide the given iterator
        loc.assign(buffer.get_end_iter())

class TermView(Gtk.TextView):
    """
    TextView-based widget for line-based terminal emulators. The widget
    has two input sources (a) input entered by the application user and
    (b) input received from a backend (usually a PTY).

    Since the widget is line-based, user input is only received after
    the user finishes input of the current line by emitting a newline
    character. Afterwards, a new-user-input signal is emitted to which
    the application should connect. To display input received from the
    backend source (e.g. a PTY) the insert_data method should be used.

    Internally, the widget tracks input through two markers. The
    _last_output_mark tracks the position in the underlying TextView
    where data from the backend source was last written. While the
    _last_mark constitues the position where user input would be
    added.

    Control characters are not line-buffered. Instead these are
    intercepted through pre-defined key bindings by Gtk and communicated
    to the application via the termios-ctrlkey signal.
    """

    def __init__(self, compfunc, limit=-1):
        # TODO: set insert-hypens to false in GTK 4
        # https://docs.gtk.org/gtk4/property.TextTag.insert-hyphens.html
        Gtk.TextView.__init__(self)

        self._textbuffer = TermBuffer(limit)
        self._textbuffer.connect("end-user-action", self.__end_user_action)
        self.set_buffer(self._textbuffer)

        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self._tabcomp = completion.TabComp(self._textbuffer, compfunc)

        self.set_monospace(True)
        self.set_input_hints(Gtk.InputHints.NO_SPELLCHECK | Gtk.InputHints.EMOJI)

        self._last_mark = self._textbuffer.create_mark(None,
                self._textbuffer.get_end_iter(), True)
        self._last_output_mark = self._last_mark

        signals = {
            "kill-after-output": self.__kill_after_output,
            "move-input-start": self.__move_input_start,
            "move-input-end": self.__move_input_end,
            "clear-view": self.__clear_view,
            "tab-completion": self.__tabcomp,
            "paste-primary": self.__paste_primary,
        }

        for name, func in signals.items():
            GObject.signal_new(name, self,
                    GObject.SIGNAL_ACTION, GObject.TYPE_NONE,
                    ())

            self.connect(name, func)

        GObject.signal_new("termios-ctrlkey", self,
                GObject.SIGNAL_ACTION, GObject.TYPE_NONE,
                (GObject.TYPE_LONG,))

        GObject.signal_new("new-user-input", self,
                GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE,
                (GObject.TYPE_PYOBJECT,))

    def insert_data(self, str, *tags):
        self._textbuffer.insert_with_tags(self._textbuffer.get_end_iter(), str, *tags)

        end = self._textbuffer.get_end_iter()
        self._last_mark = self._textbuffer.create_mark(None, end, True)
        self._last_output_mark = self._last_mark

    def flush(self):
        end = self._textbuffer.get_end_iter()

        line_start = self._textbuffer.get_iter_at_mark(self._last_output_mark)
        line = self._textbuffer.get_text(line_start, end, True)

        self.emit("new-user-input", line)

        self._last_output_mark = self._textbuffer.create_mark(None, end, True)
        self._last_mark = self._last_mark

    def __cursor_at_mark(self, mark):
        if self._textbuffer.get_has_selection():
            return False

        cur = self._textbuffer.get_iter_at_offset(self._textbuffer.props.cursor_position)
        other = self._textbuffer.get_iter_at_mark(mark)

        return cur.compare(other) == 0

    def cursor_at_out(self):
        return self.__cursor_at_mark(self._last_output_mark)

    def cursor_at_end(self):
        return self.__cursor_at_mark(self._last_mark)

    def do_backspace(self):
        # If current position is output positon ignore backspace.
        if not self.cursor_at_out():
            Gtk.TextView.do_backspace(self)

    def __end_user_action(self, buffer):
        start = buffer.get_iter_at_mark(self._last_mark)
        end = self._textbuffer.get_end_iter()

        text = buffer.get_text(start, end, True)
        if len(text) != 0 and text[-1] == "\n":
            self.flush()
        self._last_mark = buffer.create_mark(None, end, True)

        # User entered new text → reset tab completion state machine
        self._tabcomp.reset()

    def do_delete_from_cursor(self, type, count):
        # XXX: Currently, this function only ensures that word movement
        # don't move the cursor before the output point. Other movement
        # types (e.g. paragraph movements) currently might still do so.
        if type != Gtk.DeleteType.WORD_ENDS or count >= 0:
            return Gtk.TextView.do_delete_from_cursor(self, type, count)

        buf = self._textbuffer
        cur = buf.get_iter_at_offset(buf.props.cursor_position)
        out = buf.get_iter_at_mark(self._last_output_mark)

        # Only go backward by $count if there are enough characters
        # in the buffer and the movement would not go beyond the
        # last output point.
        tgt = Gtk.TextIter.copy(cur)
        if not tgt.backward_word_starts(0 - count):
            return
        elif tgt.compare(out) != 1: # tgt <= out
            # XXX: For some reason adjusting counting and changing the
            # type to Gtk.DeleteType.CHARS does not work → delete directly.
            self._textbuffer.delete_interactive(out, cur, True)
            return

        Gtk.TextView.do_delete_from_cursor(self, type, count)

    def __kill_after_output(self, textview):
        buffer = textview.get_buffer()

        start = buffer.get_iter_at_mark(self._last_output_mark)
        end = buffer.get_end_iter()

        buffer.delete(start, end)

    def __move_input_start(self, textview):
        buffer = textview.get_buffer()

        start = buffer.get_iter_at_mark(self._last_output_mark)
        buffer.place_cursor(start)

    def __move_input_end(self, textview):
        buffer = textview.get_buffer()

        end = buffer.get_iter_at_mark(self._last_mark)
        buffer.place_cursor(end)

    def __clear_view(self, textview):
        buffer = textview.get_buffer()

        # XXX: This function breaks with multi-line prompts, etc.
        end = buffer.get_iter_at_mark(self._last_output_mark)
        off = end.get_visible_line_offset()
        end.backward_chars(off)

        buffer.delete(buffer.get_start_iter(), end)

    def __tabcomp(self, textview):
        buf = textview.get_buffer()
        cur = buf.get_iter_at_offset(buf.props.cursor_position)

        # Gtk.TextCharPredicate to find start of word to be completed.
        fn = lambda x, _: str.isspace(x)

        out = buf.get_iter_at_mark(self._last_output_mark)
        if cur.backward_find_char(fn, None, out):
            cur.forward_char()
        else:
            cur.assign(out)

        self._tabcomp.next(cur)

    # See https://gitlab.gnome.org/GNOME/gtk/-/issues/352
    def __paste_primary(self, textview):
        buf = textview.get_buffer()
        buf.paste_clipboard(self._clipboard, None,
            textview.props.editable)
