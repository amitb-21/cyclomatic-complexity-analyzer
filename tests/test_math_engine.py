from types import SimpleNamespace

import pytest
from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_path_ids


def make_cfg(node_labels, edges):
    """Build a graph in the format consumed by the math engine."""
    nodes = [
        SimpleNamespace(id=node_id, label=label)
        for node_id, label in node_labels
    ]
    graph_edges = [(*edge, "") for edge in edges]
    return SimpleNamespace(nodes=nodes, edges=graph_edges)

@pytest.fixture
def simple_if_cfg():
    """
    Creates a simulated Control Flow Graph for a basic if-statement:
    1 (Entry) -> 2 (Condition)
    2 -> 3 (True branch)
    2 -> 4 (False branch)
    3 -> 5 (Exit)
    4 -> 5 (Exit)
    """
    return make_cfg(
        [
            (1, "Entry"),
            (2, "if (x > 0)"),
            (3, "x++"),
            (4, "x--"),
            (5, "Exit"),
        ],
        [(1, 2), (2, 3), (2, 4), (3, 5), (4, 5)],
    )

@pytest.fixture
def sequential_cfg():
    """Creates a simple linear CFG with no branches: 1 -> 2 -> 3"""
    return make_cfg(
        [(1, "Entry"), (2, "B"), (3, "Exit")],
        [(1, 2), (2, 3)],
    )

class TestMathEngine:
    
    def test_cyclomatic_complexity_if_statement(self, simple_if_cfg):
        """
        Cyclomatic Complexity Formula: M = E - N + 2P
        Edges (E) = 5
        Nodes (N) = 5
        Components (P) = 1
        Expected M = 5 - 5 + 2(1) = 2
        """
        complexity = calculate_complexity(simple_if_cfg)
        assert complexity["complexity"] == 2, (
            f"Expected complexity 2, got {complexity['complexity']}"
        )

    def test_cyclomatic_complexity_sequential(self, sequential_cfg):
        """
        Edges = 2, Nodes = 3, Components = 1
        Expected M = 2 - 3 + 2(1) = 1
        """
        complexity = calculate_complexity(sequential_cfg)
        assert complexity["complexity"] == 1, (
            f"Expected complexity 1, got {complexity['complexity']}"
        )

    def test_independent_paths_count(self, simple_if_cfg):
        """
        The number of linearly independent paths should equal the cyclomatic complexity (2).
        Path 1: 1 -> 2 -> 3 -> 5
        Path 2: 1 -> 2 -> 4 -> 5
        """
        paths = find_independent_path_ids(simple_if_cfg)
        assert len(paths) == 2, f"Expected 2 independent paths, got {len(paths)}"

    def test_independent_paths_sequential(self, sequential_cfg):
        """Sequential code only has 1 path: 1 -> 2 -> 3"""
        paths = find_independent_path_ids(sequential_cfg)
        assert len(paths) == 1, f"Expected 1 independent path, got {len(paths)}"

    def test_directed_path_validity(self, simple_if_cfg):
        """
        Validates that the paths returned by the engine actually flow 
        from the start node to the end node properly.
        """
        paths = find_independent_path_ids(simple_if_cfg)
        start_id = next(
            node.id for node in simple_if_cfg.nodes if node.label == "Entry"
        )
        exit_id = next(
            node.id for node in simple_if_cfg.nodes if node.label == "Exit"
        )
        valid_edges = {
            (source, target)
            for source, target, _label in simple_if_cfg.edges
        }
        
        for path in paths:
            assert path[0] == start_id, "Path must start at entry node"
            assert path[-1] == exit_id, "Path must end at exit node"

            for i in range(len(path) - 1):
                edge = (path[i], path[i+1])
                assert edge in valid_edges, f"Invalid edge {edge} found in generated path"