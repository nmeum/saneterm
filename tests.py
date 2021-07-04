import copy
import unittest

from saneterm.color import Color, ColorType
from saneterm.pty import PositionedIterator

from gi.repository import Gdk

TEST_STRING = 'foo;bar'

class TestPositionedIterator(unittest.TestCase):
    def test_lossless(self):
        it = PositionedIterator(TEST_STRING)

        self.assertEqual([x for x in it], list(TEST_STRING))
        self.assertEqual(it.wrapped, TEST_STRING)

    def test_indices(self):
        it = PositionedIterator(TEST_STRING)

        self.assertEqual(it.pos, -1)

        for x in it:
            assert x == TEST_STRING[it.pos]

            if x == ';':
                break

        self.assertEqual(it.pos, 3)

        for x in it:
            self.assertEqual(x, it.wrapped[it.pos])

        self.assertTrue(it.empty())

    def test_backtracking(self):
        it = PositionedIterator(TEST_STRING)

        semicolon_index = None

        for x in it:
            if x == ';':
                it.waypoint()
                semicolon_index = it.pos

        self.assertEqual(semicolon_index, TEST_STRING.index(';'))

        self.assertTrue(it.empty())

        with self.assertRaises(StopIteration):
            _ = it.next()

        it.backtrack()

        self.assertEqual(it.next(), ';')
        self.assertEqual(it.pos, semicolon_index)

    def test_takewhile(self):
        it = PositionedIterator(TEST_STRING)

        s = it.takewhile_greedy(lambda x: x != ';')

        self.assertEqual(s, TEST_STRING.split(';')[0])
        self.assertEqual(it.pos, len(s) - 1)
        self.assertEqual(it.next(), ';')

    def test_empty(self):
        it = PositionedIterator(TEST_STRING)

        for x in it:
            if it.pos + 1 == len(TEST_STRING):
                self.assertTrue(it.empty())

        self.assertTrue(it.empty())

        with self.assertRaises(StopIteration):
            _ = it.next()

    def test_take(self):
        length = 3
        it1 = PositionedIterator(TEST_STRING)
        it2 = PositionedIterator(TEST_STRING)

        s1 = it1.take(length)
        s2 = ''
        for x in it2:
            if it2.pos >= length:
                break
            else:
                s2 += x

        self.assertEqual(s1, s2)
        self.assertEqual(s1, TEST_STRING[0:length])

        # using take does not consume the next element!
        self.assertEqual(it1.pos, length - 1)

class TestColor(unittest.TestCase):
    def test_256_colors(self):
        """
        Check divmod based RGB value calculation against
        256 color table generation as implemented in
        XTerm's 256colres.pl.
        """
        def channel_val(c):
            return (c * 40 + 55 if c > 0 else 0) / 255

        for r in range(6):
            for g in range(6):
                for b in range(6):
                    n = 16 + (r * 36) + (g * 6) + b

                    expected = Gdk.RGBA(*map(channel_val, (r, g, b)))
                    col = Color(ColorType.NUMBERED_256, n).to_gdk()

                    self.assertTrue(
                        expected.equal(col),
                        'Color {}: expected: {}; got: {}'.format(
                            n, expected.to_string(), col.to_string()
                        )
                    )

if __name__ == '__main__':
    unittest.main()
