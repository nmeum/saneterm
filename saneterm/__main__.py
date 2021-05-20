import sys
import argparse

from terminal import *

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', metavar='CMD', type=list, nargs='*',
                        default=['sh'], help='Command to execute')

    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()

    win = Terminal(args.command)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    sys.exit(main())
