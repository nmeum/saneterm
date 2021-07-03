import os

from pty import fork
from enum import Enum, auto
from gi.repository import GLib

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
        """

        it = PositionedIterator(self.__leftover + input)
        self.__leftover = ''

        # keep track of the start position of the slice
        # we want to emit as a TEXT event
        start = 0

        # we expect a decoded string as input,
        # so we don't need to handle incremental
        # decoding here as well
        for code in it:
            # if flush_until is set, a slice of the buffer
            # from start to flush_until will be emitted as
            # a TEXT event
            flush_until = None
            # if not None, will be yielded as is, but only
            # after any necessary flushing
            special_ev = None

            # control characters flush before advancing pos
            # in order to not add them to the buffer -- we
            # want to handle them ourselves instead of
            # relying of gtk's default behavior.
            if code == '\a':
                flush_until = it.pos
                special_ev = (EventType.BELL, None)

            # at the end of input, flush if we aren't already
            if flush_until == None and it.empty():
                flush_until = it.pos + 1

            # only generate text event if it is non empty, …
            if flush_until != None and flush_until > start:
                yield (EventType.TEXT, it.wrapped[start:flush_until])

            # … but advance as if we had flushed
            if flush_until != None:
                start = it.pos + 1

            if special_ev != None:
                yield special_ev
