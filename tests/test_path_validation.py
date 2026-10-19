
import numpy as np
import pytest

from frontend.cpp.cfg_builder import CFGBuilder
from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_path_ids


EXAMPLES = [
    "examples/while_loop.cpp",
    "examples/nested_loops.cpp",
    "examples/break_continue.cpp",
    "examples/early_return.cpp",
    "examples/logical_conditions.cpp",
    "examples/nested_if.cpp",
]


def load_cfg(filename):
    with open(filename, encoding="utf-8") as file:
        return CFGBuilder().build(file.read())


def get_edge_vector(path, cfg):
    """Represent a path by the number of times it traverses each edge."""
    edge_index = {
        (source, target): index
        for index, (source, target, _) in enumerate(cfg.edges)
    }

    vector = np.zeros(len(cfg.edges), dtype=float)

    for source, target in zip(path, path[1:]):
        assert (source, target) in edge_index, (
            f"Invalid directed transition: {source} -> {target}"
        )
        vector[edge_index[(source, target)]] += 1

    return vector


@pytest.mark.parametrize("filename", EXAMPLES)
def test_paths_start_at_entry_and_end_at_exit(filename):
    cfg = load_cfg(filename)
    paths = find_independent_path_ids(cfg)
    nodes = {node.id: node for node in cfg.nodes}

    assert paths, f"No paths found for {filename}"

    for path in paths:
        assert nodes[path[0]].label == "Entry"
        assert nodes[path[-1]].label == "Exit"


@pytest.mark.parametrize("filename", EXAMPLES)
def test_paths_follow_real_directed_edges(filename):
    cfg = load_cfg(filename)
    paths = find_independent_path_ids(cfg)

    for path in paths:
        assert len(path) >= 2

        for source, target in zip(path, path[1:]):
            assert any(
                edge_source == source and edge_target == target
                for edge_source, edge_target, _ in cfg.edges
            ), f"Invalid directed transition: {source} -> {target}"


@pytest.mark.parametrize("filename", EXAMPLES)
def test_selected_path_vectors_are_linearly_independent(filename):
    cfg = load_cfg(filename)
    paths = find_independent_path_ids(cfg)

    vectors = np.array([
        get_edge_vector(path, cfg)
        for path in paths
    ])

    rank = int(np.linalg.matrix_rank(vectors))

    assert rank == len(paths), (
        f"{filename}: selected {len(paths)} paths, "
        f"but their vector rank is {rank}"
    )


@pytest.mark.parametrize("filename", EXAMPLES)
def test_selected_path_count_matches_complexity(filename):
    cfg = load_cfg(filename)
    paths = find_independent_path_ids(cfg)
    expected = calculate_complexity(cfg)["complexity"]

    assert len(paths) == expected, (
        f"{filename}: expected {expected} paths, "
        f"but found {len(paths)}"
    )
