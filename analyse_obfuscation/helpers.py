import enum
import itertools
import logging
from typing import List

import tqdm


class SpecialCharOperation(enum.Enum):
    INSERT = 1
    REPLACE = 2


class TqdmHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            tqdm.tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def ranges(i: List[int]) -> str:
    """Turns a list of integers to a string representation of the contained ranges"""
    result = []
    for _, b in itertools.groupby(enumerate(i), lambda pair: pair[1] - pair[0]):
        b = list(b)
        result.append((b[0][1], b[-1][1]))

    return ' '.join(['0x{:0>4X}..0x{:0>4X}'.format(x, y) for x, y in result])
