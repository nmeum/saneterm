import sys
from terminal import *

def main():
    win = Terminal(["dash"])
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    sys.exit(main())
