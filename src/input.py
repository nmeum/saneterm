import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

class KeyBindings():
    stylesheet = b"""
        @binding-set saneterm-key-bindings {
            bind "<ctrl>h" { "delete-from-cursor" (chars, -1) };
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
