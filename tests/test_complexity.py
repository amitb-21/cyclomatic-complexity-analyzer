
import pytest

from frontend.cpp.cfg_builder import CFGBuilder
from engine.complexity import calculate_complexity


@pytest.mark.parametrize(
    ("filename", "expected_complexity"),
    [
        ("examples/while_loop.cpp", 2),
        ("examples/nested_loops.cpp", 4),
        ("examples/break_continue.cpp", 4),
        ("examples/early_return.cpp", 2),
        ("examples/logical_conditions.cpp", 5),
        ("examples/nested_if.cpp", 3),
    ],
)
def test_cyclomatic_complexity(filename, expected_complexity):
    with open(filename, encoding="utf-8") as file:
        source = file.read()

    cfg = CFGBuilder().build(source)
    result = calculate_complexity(cfg)

    assert result["complexity"] == expected_complexity
