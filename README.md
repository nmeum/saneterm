# saneterm

Line-based terminal emulator without support for ANSI escape sequences.

## Motivation

Mainstream terminal emulators (urxvt, xterm, alacritty, …) support a
standard known as [ANSI escape sequences][wikipedia ansi]. This standard
defines several special byte sequences to provide special control
functions for terminals emulators. This includes control of the cursor,
support for different colors, et cetera. They are often used to
implement TUIs (e.g. using the [ncurses][ncurses web] library).

Many of these escape sequences operate on rows and columns and therefore
require terminal emulators to be built around a character grid were
individual cells can be modified. Historically, this was very useful to
implement UIs on physical terminals like the VT100. Nowadays this
approach feels dated and causes a variety of problems. For instance, the
concept of grapheme cluster as used in [Unicode][unicode web] is largely
incompatible with fixed-size columns. For this reason, terminal
emulator supporting the aforementioned escape sequences can never fully
support Unicode [\[1\]][variable-width glyphs].

On the other hand, a terminal emulator not supporting ANSI escape
sequences can never support TUIs. However, the idea behind `saneterm` is
that terminals shouldn't be used to implement TUIs anyhow and should
instead focus on line-based CLIs. By focusing on line-based CLIs, a
variety of features normally implemented in CLI programs themselves
(like readline-keybindings) can be implemented directly in the terminal
emulator.

## Status

Silly, buggy, and incomplete prototype implementation.

## Features

By focusing on line-based input in the terminal emulator a variety of
things can be simplified and improved. `saneterm` is presently just a
prototype and currently provides only the following features:

* Full Unicode support
* Support for [readline][readline web]-like line editing

Planned features include:

* Editing history support directly in the terminal emulator
* Features to replace pagers (search for strings, …)
* And more (see `TODO.txt`)

## Installation

This software has the following dependencies:

* [python3][python web]
* [PyGObject][PyGObject web] and [gtk+3.0][gtk web]
* [setuptools][setuptools web]

If these are installed run the following command to install `saneterm`:

	$ python3 setup.py install --optimize=1

For development setups just run `python3 saneterm/__main__.py`.

## Configuration

The terminal appearance can be configured using [Gtk's CSS][gtk css]
feature. The saneterm window widget can be selected using the CSS
selector `#saneterm`.

For example, to change the color scheme and employed font. Add the
following to your `gtk.css` configuration file located at
`$XDG_CONFIG_HOME/gtk-3.0/gtk.css`:

	#saneterm * {
		font-size: 15px;
		font-family: "Terminus";

		background-color: #181818;
		color: #d8d8d8;
	}


## FAQ

**Q:** How do I edit text on remote machines over SSH if my terminal
emulator doesn't support visual editors?

**A:** This is an interesting problem since a lot of software
relies on TUIs to be used over PTYs and SSH on remote machines. This is
mostly also an inherit flaw of Unix as it hasn't been designed with
networking and GUIs in mind. Plan 9 solves this problem through 9P file
servers, but unfortunately it has not been widely adapted and we are
stuck with Unix. In the Unix world potential solutions include
CLI-based editors (e.g. [ed][wikipedia ed]) or network protocols
tunneled over SSH connections (e.g.  [Emacs Tramp Mode][emacs tramp mode]).

**Q:** Why is this written in Python and not X?

**A:** This software is presently just a silly prototype, Python is good
for prototyping. Furthermore, Python has decent, somewhat well-documented
bindings for Gtk.

## Related Work

This work is heavily inspired by the Plan 9 terminal emulator, usage of
which is further described in the [`rio(1)` man page][rio man page].
This terminal emulator was also [ported to Unix][9term man page] as part
of [plan9port][plan9port web].

There are also a few projects which seem to share the problem statement
outlined in the Motivation but proposes different solution. Most of
which include continued support for TUIs and therefore don't benefit
from other line-based editing features. Non-complete list:

* https://github.com/withoutboats/notty
* https://github.com/christianparpart/contour

## License

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see <http://www.gnu.org/licenses/>.

[ncurses web]: https://invisible-island.net/ncurses/
[wikipedia ansi]: https://en.wikipedia.org/wiki/ANSI_escape_code
[wikipedia zwj]: https://en.wikipedia.org/wiki/Zero-width_joiner
[unicode web]: https://www.unicode.org/
[readline web]: https://tiswww.case.edu/php/chet/readline/rltop.html
[python web]: https://www.python.org/
[PyGObject web]: https://pygobject.readthedocs.io/en/latest/
[gtk web]: https://gtk.org/
[setuptools web]: https://pygobject.readthedocs.io/en/latest/
[wikipedia ed]: https://en.wikipedia.org/wiki/Ed_(text_editor)
[emacs tramp mode]: https://www.emacswiki.org/emacs/TrampMode
[variable-width glyphs]: https://gitlab.freedesktop.org/terminal-wg/specifications/-/issues/21
[rio man page]: https://9p.io/magic/man2html/1/rio
[9term man page]: https://9fans.github.io/plan9port/man/man1/9term.html
[plan9port web]: https://9fans.github.io/plan9port/
[gtk css]: https://developer.gnome.org/gtk3/stable/chap-css-overview.html
