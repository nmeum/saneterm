from enum import Enum, auto, unique

from gi.repository import Gdk

@unique
class BasicColor(Enum):
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7

# colors are (almost) the same as XTerm's default ones,
# see https://en.wikipedia.org/wiki/X11_color_names for values
BASIC_COLOR_NAMES_REGULAR = {
    BasicColor.BLACK   : "black",
    BasicColor.RED     : "red3",
    BasicColor.GREEN   : "green3",
    BasicColor.YELLOW  : "yellow3",
    BasicColor.BLUE    : "blue2",
    BasicColor.MAGENTA : "magenta3",
    BasicColor.CYAN    : "cyan3",
    BasicColor.WHITE   : "gray90",
}

BASIC_COLOR_NAMES_BRIGHT = {
    BasicColor.BLACK   : "gray50",
    BasicColor.RED     : "red",
    BasicColor.GREEN   : "green",
    BasicColor.YELLOW  : "yellow",
    BasicColor.BLUE    : "CornflowerBlue",
    BasicColor.MAGENTA : "magenta",
    BasicColor.CYAN    : "cyan",
    BasicColor.WHITE   : "white",
}

class ColorType(Enum):
    NUMBERED_8 = auto()
    NUMBERED_8_BRIGHT = auto()
    NUMBERED_256 = auto()
    TRUECOLOR = auto()

def extended_color_val(x):
    """
    Convert a 256 color cube axis index into
    its corresponding color channel value.
    """
    val = x * 40 + 55 if x > 0 else 0
    return val / 255

def int_triple_to_rgba(c):
    """
    Convert a triple of the form (r, g, b) into
    a valid Gdk.RGBA where r, g and b are integers
    in the range [0;255].
    """
    (r, g, b) = tuple(map(lambda x: x / 255, c))
    return Gdk.RGBA(r, g, b, 1)

def basic_color_to_rgba(n, bright=False):
    """
    Convert a BasicColor into a Gdk.RGBA object using
    the BASIC_COLOR_NAMES_* lookup tables. Raises an
    AssertionFailure if the conversion fails.
    """
    color = Gdk.RGBA()

    if bright:
        assert color.parse(BASIC_COLOR_NAMES_BRIGHT[n])
    else:
        assert color.parse(BASIC_COLOR_NAMES_REGULAR[n])

    return color

class Color(object):
    """
    Color represents all possible types of colors
    used in SGR escape sequences:

    * ColorType.NUMBERED_8: regular BasicColor, corresponding to
      either the 30-37 or 40-47 SGR parameters. data is always
      a member of the BasicColor enum.
    * ColorType.NUMBERED_8_BRIGHT: bright BasicColor, corresponding
      to either the 90-97 or 100-107 SGR parameters. data is always
      a member of the BasicColor enum.
    * ColorType.NUMBERED_256: a color of the 256 color palette
      supported by the SGR sequence parameters 38 and 48. data
      is always an integer in the range [0;255]
    * ColorType.TRUECOLOR: a true RGB color as supported by SGR
      sequence parameters 38 and 48. data should be a triple of
      integers in the range [0;255].
    """
    def __init__(self, t, data):
        if not isinstance(t, ColorType):
            raise TypeError("type must be ColorType")

        if t is ColorType.TRUECOLOR:
            if not type(data) is tuple:
                raise TypeError("data must be tuple for TRUECOLOR")
            if not len(data) == 3:
                raise TypeError("tuple must have 3 elements for TRUECOLOR")
        elif t is ColorType.NUMBERED_8 or t is ColorType.NUMBERED_8_BRIGHT:
            if not isinstance(data, BasicColor):
                raise TypeError(f'data must be BasicColor for {t}')
        elif t is ColorType.NUMBERED_256:
            if not type(data) is int:
                raise TypeError('data must be integer for NUMBERED_256')
            if not (data >= 0 and data < 256):
                raise TypeError('data must be in range [0;255] for NUMBERED_256')

        self.type = t
        self.data = data

    # TODO: can we prevent mutation of this object?
    def __hash__(self):
        return hash((self.type, self.data))

    def __eq__(self, other):
        return self.type == other.type and self.data == other.data

    def to_gdk(self):
        """
        Convert a Color into a Gdk.RGBA which TextTag accepts.
        The color scheme for the 16 color part uses default X11
        colors and is currently not configurable.
        """
        if self.type is ColorType.NUMBERED_8:
            return basic_color_to_rgba(self.data, bright=False)
        elif self.type is ColorType.NUMBERED_8_BRIGHT:
            return basic_color_to_rgba(self.data, bright=True)
        elif self.type is ColorType.TRUECOLOR:
            return int_triple_to_rgba(self.data)
        elif self.type is ColorType.NUMBERED_256:
            if self.data < 8:
                # normal 8 colors
                return basic_color_to_rgba(BasicColor(self.data), bright=False)
            elif self.data >= 8 and self.data < 16:
                # bright 8 colors
                return basic_color_to_rgba(BasicColor(self.data - 8), bright=True)
            elif self.data >= 16 and self.data < 232:
                # color cube which is constructed in the following manner:
                #
                # * The color number is described by the following formula:
                #   n = 16 + 36r + 6g + b
                # * r, g, b are all >= 0 and < 6
                # * The corresponding color channel value for the r, g, b
                #   values can be obtained using the following expression:
                #   x * 40 + 55 if x > 0 else 0
                #
                # This is not documented anywhere as far as I am aware.
                # The information presented here has been reverse engineered
                # from XTerm's 256colres.pl.
                tmp = self.data - 16
                (r, tmp) = divmod(tmp, 36)
                (g, b) = divmod(tmp, 6)

                triple = tuple(map(extended_color_val, (r, g, b)))
                return Gdk.RGBA(*triple)
            else:
                # grayscale in 24 steps
                c = (self.data - 232) * (1.0/24)
                return Gdk.RGBA(c, c, c, 1.0)
