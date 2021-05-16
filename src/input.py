import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import GObject

class KeyBindings():
    stylesheet = b"""
        @binding-set saneterm-key-bindings {
            bind "<ctrl>u" { "kill-after-output" () };
            bind "<ctrl>a" { "move-input-start" () };
        }

        * {
             -gtk-key-bindings: saneterm-key-bindings;
        }
    """

    def __init__(self):
        self.provider = Gtk.CssProvider()
        self.provider.load_from_data(self.stylesheet)

    def apply(self, widget):
        style_ctx = widget.get_style_context()
        style_ctx.add_provider(self.provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
