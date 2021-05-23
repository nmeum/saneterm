import sys
import argparse
import os

from .terminal import *

def get_parser():
    default_cmd = os.environ["SHELL"] if "SHELL" in os.environ else "sh"

    parser = argparse.ArgumentParser()
    parser.add_argument('command', metavar='CMD', type=str, nargs='*',
                        default=[default_cmd], help='Command to execute (defaults to $SHELL)')

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
