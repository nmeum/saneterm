from enum import Enum, auto

class PtyEventType(Enum):
    TEXT = auto()
    BELL = auto()

class PtyParser(object):
    """
    Parses a subset of special control sequences read from
    a pty device. It is somewhat high level: Given a decoded,
    proper Python string it will emit a series of events
    which just need to be reflected in the UI while any state
    is tracked in the PtyParser object.
    """
    def __init__(self):
        # no state, yet
        pass

    def parse(self, input):
        """
        Main interface of PtyParser. Given a proper decoded
        Python string , it yields a series of tuples of the
        form (PtyEventType, payload) which the caller can
        iterate through. Valid events are:

        * PtyEventType.TEXT has a string slice as its payload
          which should be appended to the terminal buffer as is.

        * PtyEventType.BELL has no payload and indicates that
          the bell character '\a' was in the terminal input.
          This usually should trigger the machine to beep
          and/or the window to set the urgent flag.
        """
        # keep track of the start and potential end position
        # of the slice we want to emit as a TEXT event
        start = 0
        pos = 0
        # TODO: can we check for the last element more efficiently?
        size = len(input)

        # we expect a decoded string as input,
        # so we don't need to handle incremental
        # decoding here as well
        for code in input:
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
                flush_until = pos
                special_ev = (PtyEventType.BELL, None)

            pos += 1

            # at the end of input, flush if we aren't already
            if flush_until == None and pos >= size:
                flush_until = pos

            # only generate text event if it is non empty, …
            if flush_until != None and flush_until > start:
                yield (PtyEventType.TEXT, input[start:flush_until])

            # … but advance as if we had flushed
            if flush_until != None:
                start = pos

            if special_ev != None:
                yield special_ev
