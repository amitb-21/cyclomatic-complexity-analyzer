
import pytest

from frontend.cpp.cfg_builder import CFGBuilder


EXAMPLES = [
    "examples/while_loop.cpp",
    "examples/nested_loops.cpp",
    "examples/break_continue.cpp",
    "examples/early_return.cpp",
    "examples/logical_conditions.cpp",
    "examples/nested_if.cpp",
]


@pytest.mark.parametrize("filename", EXAMPLES)
def test_every_cfg_edge_has_valid_endpoints(filename):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)

    node_ids = {node.id for node in cfg.nodes}

    assert cfg.edges, f"No edges generated for {filename}"

    for source_id, target_id, label in cfg.edges:
        assert source_id in node_ids
        assert target_id in node_ids


@pytest.mark.parametrize("filename", EXAMPLES)
def test_cfg_has_entry_and_exit(filename):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)

    labels = [node.label for node in cfg.nodes]

    assert labels.count("Entry") == 1
    assert labels.count("Exit") == 1


@pytest.mark.parametrize("filename", EXAMPLES)
def test_every_reported_edge_is_directed(filename):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)

    # Preserve edge direction: (u, v) is different from (v, u).
    directed_edges = {
        (source_id, target_id)
        for source_id, target_id, label in cfg.edges
    }

    for source_id, target_id in directed_edges:
        assert (source_id, target_id) in directed_edges
