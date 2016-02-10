from __future__ import print_function, unicode_literals, division, absolute_import

import random as _random

from . import utils

VERSION = '1.4.2'


def random_base32(length=16, random=_random.SystemRandom(),
                  chars=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')):
    return ''.join(
        random.choice(chars)
        for _ in range(length)
    )