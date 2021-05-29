import termios

from gi.repository import Gtk
from gi.repository import GObject

# Control keys are intercept directly (see DESIGN.md)
CTRL = {
    "<ctrl>c": termios.VINTR,
    "<ctrl>z": termios.VSUSP,
    "<ctrl>d": termios.VEOF,
}

class Bindings():
    stylesheet = b"""
        @binding-set saneterm-key-bindings {
            bind "<ctrl>u" { "kill-after-output" () };
            bind "<ctrl>a" { "move-input-start" () };
            bind "<ctrl>e" { "move-input-end" () };
            bind "<ctrl>j" { "insert-at-cursor" ("\\n") };

            bind "<ctrl>w" { "delete-from-cursor" (word-ends, -1) };
            bind "<ctrl>h" { "backspace" () };

            bind "Up" { "history-entry" (1) };
            bind "Down" { "history-entry" (-1) };

            /* Since <ctrl>c is used for VINTR, unbind <ctrl>v */
            unbind "<ctrl>v";
        }

        * {
             -gtk-key-bindings: saneterm-key-bindings;
        }
    """

    def __init__(self, widget):
        self.provider = Gtk.CssProvider()
        self.provider.load_from_data(self.stylesheet)

        style_ctx = widget.get_style_context()
        style_ctx.add_provider(self.provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def add_bind(self, key, signal, arg):
        bindings = self.__binding_set()
        # Using Gtk.BindingEntry.add_signall() would be preferable
        # https://gitlab.gnome.org/GNOME/pygobject/-/issues/474
        Gtk.BindingEntry().add_signal_from_string(bindings,
                F'bind "{key}" {{ "{signal}" ({arg}) }};')

    def __binding_set(self):
        return Gtk.BindingSet.find("saneterm-key-bindings")

