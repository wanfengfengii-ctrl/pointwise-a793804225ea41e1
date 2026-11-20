from typing import Protocol


class IntegerRandomSource(Protocol):
    def randbelow(self, upper: int) -> int:
        """Return a uniformly selected integer in the range [0, upper)."""
        raise NotImplementedError


def read_position(source: IntegerRandomSource, upper: int) -> int:
    if upper <= 0:
        raise ValueError('an empty group has no selectable position')
    position = source.randbelow(upper)
    if type(position) is not int or not 0 <= position < upper:
        raise ValueError(f'random source must return an integer in [0, {upper})')
    return position
