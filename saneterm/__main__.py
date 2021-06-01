import sys
import argparse
import os

from .terminal import *

def get_parser():
    default_cmd = os.environ["SHELL"] if "SHELL" in os.environ else "sh"

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action=argparse.BooleanOptionalAction,
                        default=False, help="Hide the vertical scrollbar")
    parser.add_argument('-l', metavar='LIMIT', type=int,
                        default=5000, help='Amount of lines to store in scroback buffer')
    parser.add_argument('command', metavar='CMD', type=str, nargs='*',
                        default=[default_cmd], help='Command to execute (defaults to $SHELL)')

    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()

    win = Terminal(args.command, limit=args.l, vscrollbar=not args.v)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    sys.exit(main())
