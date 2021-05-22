# Design

This document describe internal implementation details of `saneterm`.

## Input Handling

Input is handled line-wise, i.e. data is not written to the PTY until
the user types a newline character. This allows implementing more
advanced line editing features (e.g. readline-like keybindings) in
`saneterm`. This line-based design is inspired by [`9term`][9term man page].
Similar to `9term`, it also requires `saneterm` to disable local echo
via `termios(3)`. Applications forcing local echo (e.g. `ssh(1)`) are
currently not supported.

The line-based input forms a contiguous document collected in a
[Gtk TextBuffer][gtk textbuffer]. Text can be edited anywhere in the
buffer. In order to determine which changes should be send to the PTY,
`saneterm` records the last output point of the child process. Only text
entered beyond this output point is written to the PTY.

## Control Codes

In the Unix world, terminal emulators are usually [character-orientated][char terms].
That is, each typed character is written directly to the PTY. That
includes control characters like backspace, ctrl+z, ctrl+c, et cetera.
The current line discipline settings determine how these characters are
supposed to be interpreted. For example, `^Z` (ctrl+z) causes the line
discipline to send a `SIGTSTP` signal by default. Details of the TTY
subsystem are also further described in an [article by Linus Åkesson][tty demystified].

In the line-based context there are two possible approaches regarding
the handling of these [control characters][wikipedia c0 and c1]:

1. The corresponding ASCII code for the control character can be
   *buffered* in the line buffer. Essentially, it is treated as a normal
   character and send to the program when the user enters a newline.
   This is the approach employed by 9term.
2. Special handling for control characters could be added to the
   terminal emulator itself by *intercepting* key bindings directly. For
   instance, ctrl+c could be hardcoded to always send the interrupt
   control code. This would allow bypassing the line-based buffer and
   sending control codes to the PTY directly.

Presently, `saneterm` implements the latter approach. That is, custom
[Gtk signals][gtk signals] are defined for control commands, e.g.
`interrupt` for ctrl+c. These signals are then bound to pre-defined key
combinations, i.e. the `interrupt` signal is bound to `ctrl+c`. The
signal handler for the `interrupt` signal then determines the current ASCII
control character for `VINTR` using `termios(3)` and sends this
character to the PTY.

### Buffering

Line-based buffer of control characters, as done by `9term`, is also not
trivial to implement. It requires translating Gtk key events to ASCII
control characters and a printable representation of each control
character for the [Gtk TextView][gtk textview] used by `saneterm`.
Special care also needs to be taken to ensure that this printable
representation behaves like a single character. For instance, if the
printable representation for ctrl+z (`0x1a`) is `^Z`, a standard Gtk
`backspace` signal must remove the entire thing (i.e. the `^` and the
`Z` character) and not just the `Z` character.

### Intercepting

This approach seems more intuitiv in the Unix world. For instance, to
send a `SIGTSTP` signal one just has to press ctrl+z (as one would in a
character-orientated terminal) instead of pressing ctrl+z and then
enter. It does also have some caveats as keycodes are normally
configured using `termios(3)`. As an example, it possible to bind
`SIGINT` to a different keycode using `stty intr <keycode>` but since
`saneterm` keybindings are defined separately it would not respect that
setting. For the same reason, it is also difficult to support
noncanoical mode as defined in `termios(3)`.

The `saneterm` handlers also need to query the `termios(3)` setting on
each Gtk signal to determine the current control character, which should
be send to the PTY, using `termios(3)`.  Additionally, the line buffer
is bypassed on these signals and any data presently stored in it is
never received by the application.

[9term man page]: https://9fans.github.io/plan9port/man/man1/9term.html
[gtk textbuffer]: https://developer.gnome.org/gtk3/stable/GtkTextBuffer.html
[tty demystified]: https://www.linusakesson.net/programming/tty/
[wikipedia c0 and c1]: https://en.wikipedia.org/wiki/C0_and_C1_control_codes
[gtk signals]: https://developer.gnome.org/gtk-tutorial/stable/x159.html
[gtk textview]: https://developer.gnome.org/gtk3/stable/GtkTextView.html
[char terms]: https://en.wikipedia.org/wiki/Computer_terminal#Character-oriented_terminal
