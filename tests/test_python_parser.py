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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("def check(x):\n    assert x > 0\n    return x\n", 2),
        (
            "def classify(x):\n"
            "    match x:\n"
            "        case 0: return 0\n"
            "        case 1 | 2: return 1\n"
            "        case _: return 2\n",
            3,
        ),
        ("def choose(x, y):\n    return x if x > y else y\n", 2),
        (
            "def check(a, b, c):\n"
            "    if a and (b or c):\n"
            "        return 1\n"
            "    return 0\n",
            4,
        ),
        (
            "def check(x):\n"
            "    try:\n"
            "        if x: return 1\n"
            "        return 0\n"
            "    finally:\n"
            "        cleanup()\n",
            2,
        ),
    ],
)
def test_python_common_control_flow_complexities(tmp_path, source, expected):
    source_file = tmp_path / "control_flow.py"
    source_file.write_text(source, encoding="utf-8")

    cfg = PythonParser().build_cfg(str(source_file))

    assert calculate_complexity(cfg)["complexity"] == expected


def test_python_aggregates_all_functions_in_file(tmp_path):
    source_file = tmp_path / "multiple.py"
    source_file.write_text(
        "def first(x):\n"
        "    if x:\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "class Counter:\n"
        "    def second(self, x):\n"
        "        while x:\n"
        "            x -= 1\n"
        "        return x\n",
        encoding="utf-8",
    )

    cfg = PythonParser().build_cfg(str(source_file))

    assert calculate_complexity(cfg)["complexity"] == 4
    assert "region: first" in cfg.edge_labels.values()
    assert "region: second" in cfg.edge_labels.values()
