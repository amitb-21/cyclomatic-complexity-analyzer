
from pathlib import Path

from frontend.cpp.cfg_builder import CFGBuilder
from engine.independent_paths import find_independent_path_ids


EXAMPLES = [
    "while_loop.cpp",
    "nested_loops.cpp",
    "break_continue.cpp",
    "early_return.cpp",
    "logical_conditions.cpp",
    "nested_if.cpp",
]


def test_independent_paths_follow_real_cfg_edges():
    project_root = Path(__file__).resolve().parents[1]
    valid_examples = {
        (source, target)
        for source, target, _ in []
    }

    for example in EXAMPLES:
        source_file = project_root / "examples" / example
        code = source_file.read_text(encoding="utf-8")
        cfg = CFGBuilder().build(code)

        valid_edges = {
            (source, target)
            for source, target, _ in cfg.edges
        }

        paths = find_independent_path_ids(cfg)

        assert paths, f"No paths found for {example}"

        for path in paths:
            assert len(path) >= 2, f"Path too short in {example}"

            for source, target in zip(path, path[1:]):
                assert (source, target) in valid_edges, (
                    f"Invalid directed edge in {example}: "
                    f"{source} -> {target}"
                )
