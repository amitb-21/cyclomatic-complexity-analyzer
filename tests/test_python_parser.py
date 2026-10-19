import pytest

from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_paths
from frontend.python.parser import PythonParser


def test_python_function_builds_cfg_for_branches_and_loops(tmp_path):
    source = """def compute(values):
    total = 0
    for value in values:
        if value > 0:
            total += value
    return total
"""
    source_file = tmp_path / "sample.py"
    source_file.write_text(source, encoding="utf-8")

    cfg = PythonParser().build_cfg(str(source_file))

    assert cfg.start_node.label == "Entry"
    assert cfg.end_node.label == "Exit"
    assert calculate_complexity(cfg)["complexity"] == 3
    assert {"True", "False"}.issubset(set(cfg.edge_labels.values()))
    assert find_independent_paths(cfg)


def test_python_script_without_function_builds_cfg(tmp_path):
    source_file = tmp_path / "script.py"
    source_file.write_text(
        "value = 0\nif value:\n    value += 1\n",
        encoding="utf-8",
    )

    cfg = PythonParser().build_cfg(str(source_file))

    assert cfg.start_node.label == "Entry"
    assert cfg.end_node.label == "Exit"
    assert calculate_complexity(cfg)["complexity"] == 2


def test_python_parser_reports_syntax_errors(tmp_path):
    source_file = tmp_path / "invalid.py"
    source_file.write_text("def broken(:\n    pass\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Python source contains syntax errors"):
        PythonParser().build_cfg(str(source_file))
