import math
from fractions import Fraction

from .random_port import read_position


def cumulative_weights(probabilities: dict[tuple[str, str], Fraction]) -> list[int]:
    """Turn exact pair probabilities into integer cumulative slot weights."""
    common_denominator = 1
    for probability in probabilities.values():
        common_denominator = math.lcm(common_denominator, probability.denominator)
    cumulative: list[int] = []
    running = 0
    for probability in probabilities.values():
        running += probability.numerator * (common_denominator // probability.denominator)
        cumulative.append(running)
    return cumulative


def choose_restricted_pair(
    probabilities: dict[tuple[str, str], Fraction],
    source,
) -> tuple[str, str, Fraction]:
    cumulative = cumulative_weights(probabilities)
    total = cumulative[-1]
    position = read_position(source, total)
    pairs = list(probabilities.items())
    for index, boundary in enumerate(cumulative):
        if position < boundary:
            pair, probability = pairs[index]
            return pair[0], pair[1], probability
    raise ValueError(f'random source returned an unsupported position {position}')
