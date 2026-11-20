from decimal import Decimal
from fractions import Fraction


def parse_color_value(value: Fraction | int | str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f'invalid rational color value {value!r}') from exc
    raise ValueError('color value must be a Fraction, an integer, or rational text')


def encode_rational(value: Fraction) -> tuple[str, str]:
    # Decimal conversion keeps wide integers exact through decimal text storage.
    return format(Decimal(value.numerator), 'f'), format(Decimal(value.denominator), 'f')


def decode_rational(numerator: str, denominator: str) -> Fraction:
    return Fraction(int(Decimal(numerator)), int(Decimal(denominator)))
