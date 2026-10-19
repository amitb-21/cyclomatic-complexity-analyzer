
import pytest

from frontend.cpp.cfg_builder import CFGBuilder
from engine.independent_paths import build_fundamental_cycle_basis


EXAMPLES = [
    ("examples/while_loop.cpp", 2),
    ("examples/nested_loops.cpp", 4),
    ("examples/break_continue.cpp", 4),
    ("examples/early_return.cpp", 2),
    ("examples/logical_conditions.cpp", 5),
    ("examples/nested_if.cpp", 3),
]


def gf2_rank(vectors):
    """Calculate binary matrix rank using Gaussian elimination over GF(2)."""
    basis = {}

    for vector in vectors:
        row = set(vector)

        while row:
            pivot = max(row)

            if pivot not in basis:
                basis[pivot] = row
                break

            row.symmetric_difference_update(basis[pivot])

    return len(basis)


@pytest.mark.parametrize(("filename", "expected_dimension"), EXAMPLES)
def test_fundamental_cycle_basis(filename, expected_dimension):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)
    result = build_fundamental_cycle_basis(cfg)

    assert len(result["cycles"]) == expected_dimension
    assert result["expected_dimension"] == expected_dimension
    assert len(result["chord_edge_ids"]) == expected_dimension


@pytest.mark.parametrize(("filename", "expected_dimension"), EXAMPLES)
def test_cycle_vectors_are_linearly_independent(
    filename, expected_dimension
):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)
    result = build_fundamental_cycle_basis(cfg)

    vectors = [
        set(cycle["edge_ids"])
        for cycle in result["cycles"]
    ]

    # Each fundamental cycle must introduce a new independent vector.
    assert gf2_rank(vectors) == expected_dimension


@pytest.mark.parametrize(("filename", "expected_dimension"), EXAMPLES)
def test_each_cycle_has_its_own_chord(filename, expected_dimension):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)
    result = build_fundamental_cycle_basis(cfg)

    chord_ids = set(result["chord_edge_ids"])

    assert len(result["cycles"]) == expected_dimension

    for cycle in result["cycles"]:
        cycle_edges = set(cycle["edge_ids"])
        own_chord = cycle["chord_edge_id"]

        assert own_chord in chord_ids
        assert own_chord in cycle_edges

        # A fundamental cycle contains exactly one non-tree edge.
        assert len(cycle_edges & chord_ids) == 1
