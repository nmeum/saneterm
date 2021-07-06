#!/usr/bin/env python3

def sgr(*args):
    return '\033[' + ';'.join(map(str,args)) + 'm'

def sgr_extended(*args):
    return '\033[' + ':'.join(map(str,args)) + 'm'

def print_heading(t):
    print('\n{}{}{}\n'.format(sgr(1,4), t, sgr()))

print_heading('text style')

print('{}bold{}'.format(sgr(1), sgr(22)))
print('{}faint{}'.format(sgr(2), sgr(22)))
print('{}italic{}'.format(sgr(3), sgr(23)))
print('{}underline{}'.format(sgr(4), sgr(24)))
print('the following is concealed: {}invisible{}'.format(sgr(8), sgr(28)))
print('{}strikethrough{}'.format(sgr(9), sgr(29)))
print('{}double underline{}'.format(sgr(21), sgr(24)))

for s in [30,90,40,100]:
    print_heading(
        '16 color {}{}'.format(
            'bright ' if s > 50 else '',
            'foreground' if s % 3 == 0 else 'background',
        )
    )

    for c in range(8):
        print(
            '{}|{:2}{}'.format(
                sgr(s + c),
                c,
                sgr()
            ),
            end=''
        )

    print('')

for s in [38, 48]:
    section = 'foreground' if s == 38 else 'background'

    print_heading(
        '16 color {}'.format(section)
    )

    for y in range(2):
        for x in range(8):
            c = x + y * 8
            print(
                '{}|{:>2}{}'.format(
                    sgr_extended(s, 5, c),
                    c,
                    sgr(s + 1)
                ),
                end=''
            )

        print('')

    print_heading('6 * 6 * 6 cube color {}'.format(section))

    for y in range(6):
        for x in range(36):
            c = 16 + x + y * 36
            print(
                '{}|{:>3}{}'.format(
                    sgr_extended(s, 5, c),
                    c,
                    sgr(s + 1)
                ),
                end=''
            )
        print('')

    print_heading('grayscale {}'.format(section))

    for c in range(232, 256):
        print(
            '{}|{:>3}{}'.format(
                sgr_extended(s, 5, c),
                c,
                sgr(s + 1)
            ),
            end=''
        )
    print('')


print_heading('16 color combinations')

print('  |' + '|'.join(map(lambda x: '{:<4}'.format(x), range(16))))
for f in range(16):
    print(f'{f:>2}', end='')

    for b in range(16):
        print(
            '{}{}|test{}'.format(
                sgr_extended(38, 5, f),
                sgr_extended(48, 5, b),
                sgr(39, 49)
            ),
            end=''
        )
    print('')
