import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import GObject

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

    def __init__(self):
        Gtk.TextView.__init__(self)

        self.set_monospace(True)
        self.set_input_hints(Gtk.InputHints.NO_SPELLCHECK | Gtk.InputHints.EMOJI)

        self._textbuffer = self.get_buffer()
        self._textbuffer.connect("end-user-action", self.__end_user_action)

        self._last_mark = self._textbuffer.create_mark(None,
                self._textbuffer.get_end_iter(), True)
        self._last_output_mark = self._last_mark

        signals = {
            "kill-after-output": self.__kill_after_output,
            "move-input-start": self.__move_input_start,
            "move-input-end": self.__move_input_end,
        }

        for signal in signals.items():
            name, func = signal
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

    def cursor_at_out(self):
        cur = self._textbuffer.get_iter_at_offset(self._textbuffer.props.cursor_position)
        out = self._textbuffer.get_iter_at_mark(self._last_output_mark)

        return cur.compare(out) == 0

    def cursor_at_end(self):
        cur = self._textbuffer.get_iter_at_offset(self._textbuffer.props.cursor_position)
        end = self._textbuffer.get_iter_at_mark(self._last_mark)

        return cur.compare(end) == 0

    def do_backspace(self):
        # If current position is output positon ignore backspace.
        if not self.cursor_at_out():
            Gtk.TextView.do_backspace(self)

    def __end_user_action(self, buffer):
        start = buffer.get_iter_at_mark(self._last_mark)
        end = self._textbuffer.get_end_iter()

        text = buffer.get_text(start, end, True)
        if text == "\n":
            self.flush()
        else:
            self._last_mark = buffer.create_mark(None, end, True)

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
