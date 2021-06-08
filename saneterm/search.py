from gi.repository import Gtk

class SearchBar(Gtk.SearchBar):
    "SearchBar implements Gtk.SearchBar on a Gtk.TextBuffer."

    BG_COLOR = "yellow"
    FG_COLOR = "black"

    def __init__(self, view):
        Gtk.SearchBar.__init__(self)

        self.__view = view
        self.__buffer = view.get_buffer()

        self.__match = None
        self.__tag = self.__buffer.create_tag("search-match",
                background=self.BG_COLOR,
                foreground=self.FG_COLOR)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        style_ctx = hbox.get_style_context()
        style_ctx.add_class("linked")
        style_ctx.add_class("raised")
        self.add(hbox)

        search_entry = Gtk.SearchEntry.new()
        search_entry.set_width_chars(32)
        search_entry.connect("search-changed", self.__search_changed)
        search_entry.connect("next-match", self.__next_match)
        search_entry.connect("previous-match", self.__prev_match)
        hbox.pack_start(search_entry, True, True, 0)

        self.__nextbtn, self.__prevbtn = self.__create_nav_buttons(search_entry, hbox)

        self.set_show_close_button(True)
        self.connect_entry(search_entry)

    def __create_nav_buttons(self, search_entry, box):
        def button_callback(button, dir):
            signal = "previous-match" if dir == "up" else "next-match"
            search_entry.emit(signal)

        buttons = []
        for dir in ["up", "down"]:
            button = Gtk.Button.new_from_icon_name(F"go-{dir}-symbolic", Gtk.IconSize.MENU)
            button.set_sensitive(False)
            button.connect("clicked", button_callback, dir)

            box.add(button)
            buttons.append(button)

        return tuple(buttons)

    def __find_match(self, entry, start, forward=True):
        buf = self.__buffer
        text = entry.get_text()

        # Remove old match.
        buf.remove_tag(self.__tag,
                buf.get_start_iter(),
                buf.get_end_iter())

        if forward:
            self.__match = start.forward_search(text, 0, None)
        else:
            self.__match = start.backward_search(text, 0, None)

        if self.__match:
            mstart, mend = self.__match
            buf.apply_tag(self.__tag, mstart, mend)
            self.__view.scroll_to_iter(mstart, 0.1, False, 0.0, 0.0)

        return self.__match

    def __search_changed(self, entry):
        found = self.__find_match(entry, self.__buffer.get_start_iter())

        self.__nextbtn.set_sensitive(not found is None)
        self.__prevbtn.set_sensitive(not found is None)

    def __next_match(self, entry):
        # Wrap around if no match was found previously.
        if self.__match is None:
            start = self.__buffer.get_start_iter()
        else:
            _, start = self.__match

        self.__find_match(entry, start)

    def __prev_match(self, entry):
        # Wrap around if no match was found previously.
        if self.__match is None:
            start = self.__buffer.get_end_iter()
        else:
            start, _ = self.__match

        self.__find_match(entry, start, forward=False)
