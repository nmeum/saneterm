import os

class TabComp():
    "Implements a state machine for tab completions on a Gtk.TextBuffer"

    def __init__(self, buffer, compfn):
        self.__buffer = buffer
        self.__compfn = compfn

        self._tabcomp_mark = None
        self._tabcomp_index = 0

    def reset(self):
        """Invalidates any cached completion results. Should be called
           when the user presses any key other than the key configured
           for tab completions."""

        self._tabcomp_mark = None

    def next(self, start):
        "Completes the word starting at the given start iterator."

        buffer = self.__buffer

        # Distinguish two cases:
        #   1. This is the first time the user pressed tab.
        #      If so: Determine input between word start and end.
        #   2. User is switching through generated matches.
        #      If so: Determine input between word start and _tabcomp_mark.
        if self._tabcomp_mark is None:
            # Reset has been called → invalidate completion cache
            self._tabcomp_matches = None
            self._tabcomp_index = 0

            end = buffer.get_iter_at_offset(buffer.props.cursor_position)
            self._tabcomp_mark = buffer.create_mark(None, end, True)
        else:
            end = buffer.get_iter_at_mark(self._tabcomp_mark)

        # Extract text, regenerate completion results for
        # given text if cache has been invalidated above.
        text = buffer.get_text(start, end, True)
        if self._tabcomp_matches is None:
            self._tabcomp_matches = self.__compfn(text)
            self._tabcomp_matches.append("") # original text
        c = self._tabcomp_matches[self._tabcomp_index]

        # Insert the matched completion text and delete
        # text potentially remaining from older completion.
        buffer.insert(end, c)
        cursor = buffer.get_iter_at_offset(buffer.props.cursor_position)
        buffer.delete(end, cursor)

        # Advance current index in matches and wrap-around.
        self._tabcomp_index = (self._tabcomp_index + 1) % len(self._tabcomp_matches)

class FileName():
    "Provides file name completions relative to a given directory."

    def __init__(self, cwd):
        self.__cwd = cwd

    def get_matches(self, input):
        # Preferably, we would expand ~ to $HOME on tab since the
        # application may not expand ~ itself. However, the current
        # completion setup just allows appending characters to the end.
        input = os.path.expanduser(input)

        if input.find("/") != -1:
            base = os.path.dirname(input)
            prefix = os.path.basename(input)

            if not os.path.isabs(input):
                base = os.path.join(self.__cwd, base)
        else:
            base = self.__cwd
            prefix = input

        return self.__get_matches(base, prefix)

    def __get_matches(self, base, prefix):
        if not os.path.isdir(base):
            return []

        matches = []
        with os.scandir(base) as it:
            for entry in it:
                name = entry.name
                if prefix != "" and not name.startswith(prefix):
                    continue
                if entry.is_dir():
                    name += "/"

                # Strip prefix from name
                name = name[len(prefix):]
                matches.append(name)

        # Ensure that shortest matches are suggested first
        matches.sort(key=len)

        return matches
