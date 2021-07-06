import os
import re

from pty import fork
from .color import Color, ColorType, BasicColor
from enum import Enum, auto
from gi.repository import GLib, Pango

TERM = "dumb"

class Source(GLib.Source):
    master = -1

    def __init__(self, cmd):
        GLib.Source.__init__(self)
        self.cmd = cmd
        self.tag = None

    def prepare(self):
        if self.master != -1:
            return False, -1

        pid, self.master = fork()
        if pid == 0:
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

class EventType(Enum):
    TEXT = auto()
    BELL = auto()
    TEXT_STYLE = auto()

class TextStyleChange(Enum):
    """
    Each TextStyleChange describes a way in which escape
    sequences may influence the way text is displayed.
    Together with an additional value (True or False,
    a color, an enum from Pango, …) a TextStyleChange
    can represent the actual impact an escape sequence
    has on the font rendering.

    The important invariant here is that all associated
    represented changes are _mutually exclusive_:
    E. g. (TextStyleChange.ITALIC, True) and
    (TextStyleChange.ITALIC, False) can't be applied at
    the same time — one will replace the other.
    This invariant greatly simplifies state tracking.
    """

    # resets the display style to an arbitrary default
    # No associated value
    RESET = auto()
    # Enables/disables italic text
    # associated with a boolean
    ITALIC = auto()
    # Enables/disables text being crossed out
    # associated with a boolean
    STRIKETHROUGH = auto()
    # Describes weight of the font to use
    # associated with a Pango.Weight enum
    WEIGHT = auto()
    # Disables or enables an underline style
    # associated with a Pango.Underline enum
    UNDERLINE = auto()
    # Hides/shows the text. If hidden, should
    # not be readable, but in many implementations
    # the text is still able to be copied.
    # associated with a boolean
    CONCEALED = auto()
    # Sets the text's color or resets
    # it to a default if None.
    # associated with either None or a Color
    FOREGROUND_COLOR = auto()
    # Sets the text's background color or resets
    # it to a default if None.
    # associated with either None or a Color
    BACKGROUND_COLOR = auto()

class PositionedIterator(object):
    """
    Wrapper class which implements the iterator interface
    for a string. In contrast to the default implementation
    it works by tracking an index in the string internally.

    This allows the following additional features:

    * Checking whether the iterator has any elements left
      using empty()
    * Jumping back to a previous point via backtrack()

    The object exposes the following attributes:

    * pos: the index of the last element received via __next__()
    * wrapped: the string used for construction
    """
    def __init__(self, s):
        # always points to the position of the element
        # just received via __next__()
        self.pos = -1
        self.wrapped = s

        self.waypoints = []

    def waypoint(self):
        """
        Mark the index backtrack() should jump to when called.
        Calling this will make the character received by __next__()
        after calling backtrack() at any point in the future be
        the same which was last received via __next__() before
        calling waypoint().

        Counterintutively, this means that pos immediately after
        calling waypoint() will be greater than right after
        calling backtrack() subsequently.

        This allows you to decide whether or not to set a waypoint
        after inspecting an element which is useful when writing
        parsers:

        def example(s):
          it = PositionedIterator(s)

          ignore_colon = False

          for x in it:
            if ignore_colon:
              ignore_colon = False
              # do nothing
            elif x == ':':
              it.waypoint()

              if x.next() == ' ':
                # do stuff …
              else:
                it.backtrack()
                ignore_colon = True
        """
        # TODO: maybe don't support calling waypoint if pos == -1
        self.waypoints.append(max(self.pos - 1, -1))

    def backtrack(self):
        """See documentation of waypoint()"""
        self.pos = self.waypoints.pop()

    def next(self):
        """Shortcut for __next__()"""
        return self.__next__()

    def take(self, n):
        """
        Consume n elements of the iterator and return them as a string slice.
        """
        start = self.pos + 1

        for _ in range(n):
            _ = self.__next__()

        end = self.pos + 1

        return self.wrapped[start:end]

    def takewhile_greedy(self, f):
        """
        Consume elements while a given predicate returns True and
        return them as a string slice. takewhile_greedy() expects
        the predicate to return False at least once before the end
        of input and will otherwise raise a StopIteration condition.

        Thus using takewhile_greedy() only makes sense if whatever
        your parsing is terminated in some way:

        def example(s):
          foo = takewhile_greedy(lambda x: x != ';')

        example("foo")  # fails
        example("foo;") # succeeds, but doesn't consume ';'

        (In a real example you'd also consume the semicolon)
        """
        x = self.__next__()
        start = self.pos

        while f(x):
            x = self.__next__()

        end = self.pos
        self.pos -= 1

        return self.wrapped[start:end]

    def empty(self):
        """
        Check if the iterator has no elements left
        without consuming the next item (if any).
        """
        return self.pos + 1 == len(self.wrapped)

    def __iter__(self):
        return self

    def __next__(self):
        self.pos += 1

        try:
            return self.wrapped[self.pos]
        except IndexError:
            self.pos -= 1
            raise StopIteration

def csi_parameter_byte(c):
    """
    Check if the given unicode character is a CSI sequence
    parameter byte. See ECMA-48 (5th edition) Section 5.4.
    """
    cp = ord(c)
    return cp >= 0x30 and cp <= 0x3f

def csi_intermediate_byte(c):
    """
    Check if the given unicode character is a CSI sequence
    intermediate byte. See ECMA-48 (5th edition) Section 5.4.
    """
    cp = ord(c)
    return cp >= 0x20 and cp <= 0x2f

def csi_final_byte(c):
    """
    Check if the given unicode character is a CSI sequence
    final byte. See ECMA-48 (5th edition) Section 5.4.
    """
    cp = ord(c)
    return cp >= 0x40 and cp <= 0x7e

def parse_extended_color(iterator):
    """
    Parse extended color sequences (CSI [ 38 and CSI [ 48).
    Takes an iterator which has already consumed the initial
    SGR sequence type argument and returns a Color.
    On failure an AssertionError is raised.

    Relevant standards:
    * Definition of the SGR extended color escape sequence:
      ITU-T Rec. T.416 | ISO/IEC 8613-6
      https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-T.416-199303-I!!PDF-E&type=items
    * Full definition of the colour specification including the “colour space id”:
      ITU-T Rec. T.412 | ISO/IEC 8613-2
      https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-T.412-199303-I!!PDF-E&type=items
    """
    args = list(iterator)

    if len(args) == 0:
        raise AssertionError("too few arguments")

    if args[0] == '5':
        # 256 color
        assert len(args) == 2

        try:
            return Color(
                ColorType.NUMBERED_256,
                int(args[1])
            )
        except ValueError:
            raise AssertionError("unexpected non-integer")
    elif args[0] == '2':
        # truecolor
        if len(args) == 4:
            channels = tuple(args[1:4])
        elif len(args) >= 5:
            # TODO: handle color space id and tolerance values
            channels = tuple(args[2:5])
        else:
            raise AssertionError("too few arguments")

        try:
            return Color(
                ColorType.TRUECOLOR,
                tuple(int(c) for c in channels)
            )
        except ValueError:
            raise AssertionError("unexpected non-integer")
    elif args[0] == '0':
        # The standard specifies this as “implementation defined”,
        # so we define this as color reset
        return None
    else:
        # TODO: support
        #
        #   1   transparent
        #   3   CMY
        #   4   CMYK
        #
        # … but who needs these?
        raise AssertionError("unsupported extended color")


def parse_sgr_sequence(params, special_evs):
    """
    SGR (Select Graphic Rendition) sequence:
    any number of numbers separated by ';'
    which change the current text presentation.
    If the parameter string is empty, a single '0'
    is implied.

    We support a subset of the core SGR sequences
    as specified by ECMA-48. Most notably we also
    support the common additional bright color
    sequences. This also justifies not to implement
    the strange behavior of choosing brighter colors
    when the current text is bold.

    We also support ':' as a separator which is
    only necessary for extended color sequences
    as specified in ITU-T Rec. T.416 | ISO/IEC 8613-6
    (see also parse_extended_color()). Actually
    those sequences _must_ use colons and semicolons
    would be invalid. In reality, however, the
    incorrect usage of semicolons seems to be much
    more common. Thus we are extremely lenient and
    allow both ':' and ';' as well as a mix of both
    as separators.
    """
    args = re.split(r'[:;]', params)

    arg_it = iter(args)
    for arg in arg_it:
        if len(arg) == 0:
            # empty implies 0
            sgr_type = 0
        else:
            try:
                sgr_type = int(arg)
            except ValueError:
                raise AssertionError("Invalid Integer")

        change_payload = None

        # Not supported:
        #   5-6     blink
        #   7       invert
        #   10      default font
        #   11-19   alternative font
        #   20      blackletter font
        #   25      disable blinking
        #   26      proportional spacing
        #   27      disable inversion
        #   50      disable proportional spacing
        #   51      framed
        #   52      encircled
        #   53      overlined (TODO: implement via GTK 4 TextTag)
        #   54      neither framed nor encircled
        #   55      not overlined
        #   60-65   ideograms (TODO: find out what this is supposed to do)
        #   58-59   underline color, non-standard
        #   73-65   sub/superscript, non-standard (TODO: via scale and rise)
        if sgr_type == 0:
            change_payload = (TextStyleChange.RESET, None)
        elif sgr_type == 1:
            change_payload = (TextStyleChange.WEIGHT, Pango.Weight.BOLD)
        elif sgr_type == 2:
            change_payload = (TextStyleChange.WEIGHT, Pango.Weight.THIN)
        elif sgr_type == 3:
            change_payload = (TextStyleChange.ITALIC, True)
        elif sgr_type == 4:
            change_payload = (TextStyleChange.UNDERLINE, Pango.Underline.SINGLE)
        elif sgr_type == 8:
            change_payload = (TextStyleChange.CONCEALED, True)
        elif sgr_type == 9:
            change_payload = (TextStyleChange.STRIKETHROUGH, True)
        elif sgr_type == 21:
            change_payload = (TextStyleChange.UNDERLINE, Pango.Underline.DOUBLE)
        elif sgr_type == 22:
            change_payload = (TextStyleChange.WEIGHT, Pango.Weight.NORMAL)
        elif sgr_type == 23:
            # also theoretically should disable blackletter
            change_payload = (TextStyleChange.ITALIC, False)
        elif sgr_type == 24:
            change_payload = (TextStyleChange.UNDERLINE, Pango.Underline.NONE)
        elif sgr_type == 28:
            change_payload = (TextStyleChange.CONCEALED, False)
        elif sgr_type == 29:
            change_payload = (TextStyleChange.STRIKETHROUGH, False)
        elif sgr_type >= 30 and sgr_type <= 37:
            change_payload = (
                TextStyleChange.FOREGROUND_COLOR,
                Color(
                    ColorType.NUMBERED_8,
                    BasicColor(sgr_type - 30)
                )
            )
        elif sgr_type == 38:
            try:
                change_payload = (
                    TextStyleChange.FOREGROUND_COLOR,
                    parse_extended_color(arg_it)
                )
            except AssertionError:
                # TODO: maybe fail here?
                pass
        elif sgr_type == 39:
            change_payload = (TextStyleChange.FOREGROUND_COLOR, None)
        elif sgr_type >= 40 and sgr_type <= 47:
            change_payload = (
                TextStyleChange.BACKGROUND_COLOR,
                Color(
                    ColorType.NUMBERED_8,
                    BasicColor(sgr_type - 40)
                )
            )
        elif sgr_type == 48:
            try:
                change_payload = (
                    TextStyleChange.BACKGROUND_COLOR,
                    parse_extended_color(arg_it)
                )
            except AssertionError:
                # TODO: maybe fail here?
                pass
        elif sgr_type == 49:
            change_payload = (TextStyleChange.BACKGROUND_COLOR, None)
        elif sgr_type >= 90 and sgr_type <= 97:
            change_payload = (
                TextStyleChange.FOREGROUND_COLOR,
                Color(
                    ColorType.NUMBERED_8_BRIGHT,
                    BasicColor(sgr_type - 90)
                )
            )
        elif sgr_type >= 100 and sgr_type <= 107:
            change_payload = (
                TextStyleChange.BACKGROUND_COLOR,
                Color(
                    ColorType.NUMBERED_8_BRIGHT,
                    BasicColor(sgr_type - 100)
                )
            )

        if change_payload != None:
            special_evs.append((EventType.TEXT_STYLE, change_payload))

def parse_csi_sequence(it, special_evs):
    """
    Parses control sequences which begin with a
    Control Sequence Introducer (CSI) as specified
    in ECMA-48, section 5.4.
    Supported escape sequences append events to
    special_evs while unsupported ones are ignored,
    and thus filtered out.
    """
    params = it.takewhile_greedy(csi_parameter_byte)
    inters = it.takewhile_greedy(csi_intermediate_byte)
    final = it.next()

    assert csi_final_byte(final)

    # Unsupported CSI sequences are ignored which reduces
    # the noise from unsupported sequences
    if final == 'm':
        parse_sgr_sequence(params, special_evs)

class Parser(object):
    """
    Parses a subset of special control sequences read from
    a pty device. It is somewhat high level: Given a decoded,
    proper Python string it will emit a series of events
    which just need to be reflected in the UI while any state
    is tracked in the Parser object.
    """
    def __init__(self):
        # unparsed output left from the last call to parse
        self.__leftover = ''

    def parse(self, input):
        """
        Main interface of Parser. Given a proper decoded
        Python string , it yields a series of tuples of the
        form (EventType, payload) which the caller can
        iterate through. Valid events are:

        * EventType.TEXT has a string slice as its payload
          which should be appended to the terminal buffer as is.

        * EventType.BELL has no payload and indicates that
          the bell character '\a' was in the terminal input.
          This usually should trigger the machine to beep
          and/or the window to set the urgent flag.

        Parsed control sequences are guaranteed to never
        appear in a TEXT event. This is also true for
        escape sequences which don't cause an event to
        be generated. This is true for all CSI escape
        sequences at the moment which are filtered out
        from saneterm's output in this way.
        """

        it = PositionedIterator(self.__leftover + input)
        self.__leftover = ''

        # keep track of the start position of the slice
        # we want to emit as a TEXT event
        start = 0

        # this is set by the parser before backtracking if
        # an ANSI escape sequence should be ignored, e. g.
        # if we don't support it
        ignore_esc = False

        # we expect a decoded string as input,
        # so we don't need to handle incremental
        # decoding here as well
        for code in it:
            # if flush_until is set, a slice of the buffer
            # from start to flush_until will be emitted as
            # a TEXT event
            flush_until = None
            # if not empty, each of its elements will be yield
            # one by one, but only after any necessary flushing
            special_evs = []

            # control characters flush before advancing pos
            # in order to not add them to the buffer -- we
            # want to handle them ourselves instead of
            # relying of gtk's default behavior.
            if code == '\a':
                flush_until = it.pos
                special_evs.append((EventType.BELL, None))
            elif code == '\033':
                # ignore_esc can be set if we encounter a '\033'
                # which is followed by a sequence we don't understand.
                # In that case we'll jump back to the '\033', but just
                # treat it as if it was an ordinary character.
                if ignore_esc:
                    ignore_esc = False
                else:
                    flush_until = it.pos

                    # if parsing fails we'll return to this point
                    it.waypoint()

                    try:
                        if it.next() == '[':
                            parse_csi_sequence(it, special_evs)
                        else:
                            # we only parse CSI sequences for now, all other
                            # sequences will be rendered as text to the terminal.
                            # This probably should change in the future since
                            # we also want to filter out, e. g. OSC sequences
                            ignore_esc = True

                    except AssertionError:
                        # AssertionError indicates a parse error, we'll render
                        # a escape sequence we can't parse verbatim for now
                        ignore_esc = True

                    except StopIteration:
                        # the full escape sequence wasn't contained in
                        # this chunk of input, so we'll parse it next time.
                        # Since we flush up to the escape sequence, we know
                        # where it started. The parser loop will exit at the
                        # end of this iteration because the iterator is
                        # exhausted.
                        self.__leftover = it.wrapped[flush_until:]

                        # prevent a backtrack which would break
                        # (this can't happen in the current code, but is
                        # a subtle problem in practise, so this line could
                        # save us some debugging later)
                        ignore_esc = False

                    # if we want to add the (invalid) escape sequence to the
                    # TermView verbatim, we'll need to backtrack as well as well
                    if ignore_esc:
                        it.backtrack()


            # at the end of input, flush if we aren't already
            if flush_until == None and it.empty():
                flush_until = it.pos + 1

            # only generate text event if it is non empty, …
            if flush_until != None and flush_until > start:
                yield (EventType.TEXT, it.wrapped[start:flush_until])

            # … but advance as if we had flushed
            if flush_until != None:
                start = it.pos + 1

            if len(special_evs) > 0:
                for ev in special_evs:
                    yield ev
