from fractions import Fraction


def squared_color_difference(left: Fraction, right: Fraction) -> Fraction:
    difference = left - right
    return difference * difference
