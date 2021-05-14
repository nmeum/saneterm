from terminal import *

if __name__ == "__main__":
    win = Terminal(["dash"])
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
