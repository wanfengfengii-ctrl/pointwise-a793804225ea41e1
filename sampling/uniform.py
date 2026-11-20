from .random_port import IntegerRandomSource, read_position


def choose_uniform_pair(
    left: tuple[str, ...],
    right: tuple[str, ...],
    source: IntegerRandomSource,
) -> tuple[str, str]:
    left_position = read_position(source, len(left))
    right_position = read_position(source, len(right))
    return left[left_position], right[right_position]
