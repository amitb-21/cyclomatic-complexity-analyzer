import os
import pytest
from frontend.cpp.parser import CppParser
from engine.complexity import calculate_complexity

# Construct the path to the examples directory
# This assumes your folder structure is:
# /cyclomatic-complexity-analyzer
# ├── examples/
# └── tests/
#     └── test_integration.py
EXAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "examples"))

# Dynamically gather all .cpp files in the examples folder
EXAMPLE_FILES = []
if os.path.exists(EXAMPLES_DIR):
    EXAMPLE_FILES = [
        os.path.join(EXAMPLES_DIR, f) 
        for f in os.listdir(EXAMPLES_DIR) 
        if f.endswith('.cpp')
    ]

# If the examples folder is missing or empty, this test will just be skipped automatically
@pytest.mark.skipif(not EXAMPLE_FILES, reason="No C++ example files found in the examples/ directory.")
@pytest.mark.parametrize("file_path", EXAMPLE_FILES)
def test_examples_run_without_crashing(file_path):
    """
    End-to-end integration test: 
    Ensures the parser and math engine can process every real example 
    file without throwing an exception or returning empty graphs.
    """
    parser = CppParser()
    
    try:
        # 1. Build the CFG from the real file
        cfg = parser.build_cfg(file_path)
        
        # Verify the CFG was actually built
        assert cfg is not None, f"Failed to build CFG for {os.path.basename(file_path)}"
        assert len(cfg.nodes) > 0, f"CFG is empty for {os.path.basename(file_path)}"
        
        # 2. Feed the CFG into the math engine
        complexity = calculate_complexity(cfg)
        
        # Basic sanity checks on the math results
        assert complexity["complexity"] >= 1, (
            f"Complexity should be at least 1 for {os.path.basename(file_path)}"
        )
        
    except Exception as e:
        # If any part of the pipeline crashes, the test fails and prints the error
        pytest.fail(f"Pipeline crashed on {os.path.basename(file_path)}: {e}")


@pytest.mark.parametrize(
    ("filename", "expected_complexity"),
    [
        ("kadane.cpp", 4),
        ("binary_search.cpp", 4),
        ("knapsack_dp.cpp", 5),
    ],
)
def test_algorithm_example_complexities(filename, expected_complexity):
    file_path = os.path.join(EXAMPLES_DIR, filename)
    cfg = CppParser().build_cfg(file_path)

    result = calculate_complexity(cfg)

    assert result["complexity"] == expected_complexity