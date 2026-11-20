"""Exact rational marginals over an allowed-pair list.

A restricted plan draws one ordered (left, right) pair.  Every specimen on
either side must have marginal inspection probability exactly ``1/n`` while
every allowed pair keeps a strictly positive probability and every other pair
has probability zero.

Such a distribution exists exactly when every allowed edge belongs to at least
one perfect matching of the bipartite graph (an edge outside every perfect
matching can never receive positive probability under the marginals).  The
construction below enumerates, for each allowed edge in input order, one
perfect matching containing it, then mixes the distinct matchings uniformly.
For an edge covered by ``c_e`` of the ``S`` selected matchings this gives
``p_e = c_e / (S*n)``; every left and right specimen is matched once per
matching, so every marginal is exactly ``1/n``.
"""
from collections.abc import Sequence
from fractions import Fraction


Edge = tuple[int, int]


def _find_perfect_matching(
    adjacency: Sequence[Sequence[int]], size: int, forced: Edge | None = None,
) -> tuple[int, ...] | None:
    """Return ``matching`` with ``matching[left] == right`` for every left."""
    match_right = [-1] * size
    if forced is not None:
        forced_left, forced_right = forced
        if forced_right not in adjacency[forced_left]:
            return None
        match_right[forced_right] = forced_left

    def augment(left: int) -> bool:
        for right in adjacency[left]:
            if seen[right]:
                continue
            seen[right] = True
            holder = match_right[right]
            if holder == -1 or augment(holder):
                match_right[right] = left
                return True
        return False

    for left in range(size):
        if forced is not None and left == forced[0]:
            continue
        seen = [False] * size
        if forced is not None:
            seen[forced[1]] = True
        if not augment(left):
            return None

    matching = [-1] * size
    for right, left in enumerate(match_right):
        if left == -1:
            return None
        matching[left] = right
    return tuple(matching)


def build_restricted_distribution(
    allowed_edges: Sequence[Edge], size: int,
) -> dict[Edge, Fraction] | None:
    """Build the frozen distribution, or ``None`` when the constraints conflict."""
    adjacency: list[list[int]] = [[] for _ in range(size)]
    for left, right in allowed_edges:
        adjacency[left].append(right)
    if _find_perfect_matching(adjacency, size) is None:
        return None

    selected: dict[tuple[int, ...], None] = {}
    for edge in allowed_edges:
        matching = _find_perfect_matching(adjacency, size, forced=edge)
        if matching is None:
            return None
        selected.setdefault(matching, None)

    matchings = tuple(selected)
    coverage = {edge: 0 for edge in allowed_edges}
    for matching in matchings:
        for left, right in enumerate(matching):
            edge = (left, right)
            if edge in coverage:
                coverage[edge] += 1

    weight = Fraction(1, len(matchings) * size)
    distribution = {edge: coverage[edge] * weight for edge in allowed_edges}
    if any(probability <= 0 for probability in distribution.values()):
        return None
    return distribution
