from gi.repository import Gtk
from gi.repository import GObject

from . import completion

class LimitTextBuffer(Gtk.TextBuffer):
    """
    Buffer which stores a limit amount of lines. If the limit is -1
    an unlimited amount of lines is stored. Old lines are deleted
    automatically if the limit is exceeded.
    """

    def __init__(self, limit):
        Gtk.TextBuffer.__init__(self)

        if limit == -1:
            return # unlimited

        self.limit = limit
        self.connect_after("insert-text", self.__insert_text)

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

        self._textbuffer = LimitTextBuffer(limit)
        self._textbuffer.connect("end-user-action", self.__end_user_action)
        self.set_buffer(self._textbuffer)

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

    def insert_data(self, str):
        self._textbuffer.insert(self._textbuffer.get_end_iter(), str)

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

    # XXX: Can maybe be removed in favor of do_delete_from_cursor.
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
        # If the type is GTK_DELETE_CHARS, GTK+ deletes the selection.
        if type == Gtk.DeleteType.CHARS:
            Gtk.TextView.do_delete_from_cursor(self, type, count)
            return

        buf = self._textbuffer
        cur = buf.get_iter_at_offset(buf.props.cursor_position)
        out = buf.get_iter_at_mark(self._last_output_mark)

        # Only go backward by $count chars if there are enough
        # characters in the buffer and the movement would not
        # go beyond the last output point.
        if cur.backward_chars(count):
            return
        elif cur.compare(out) != 1: # cur <= out
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
