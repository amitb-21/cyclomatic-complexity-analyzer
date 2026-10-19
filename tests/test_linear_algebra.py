
import pytest

from engine.linear_algebra import binary_rank


def test_empty_vectors_have_zero_rank():
    assert binary_rank([]) == 0


def test_independent_vectors():
    vectors = [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
    ]
    assert binary_rank(vectors) == 3


def test_dependent_vectors():
    vectors = [
        [1, 0, 1],
        [0, 1, 1],
        [1, 1, 0],
    ]
    assert binary_rank(vectors) == 2


def test_repeated_vectors():
    assert binary_rank([[1, 0], [1, 0]]) == 1


def test_inconsistent_vector_lengths():
    with pytest.raises(ValueError):
        binary_rank([[1, 0], [1]])


def test_nonbinary_values():
    with pytest.raises(ValueError):
        binary_rank([[1, 2]])
