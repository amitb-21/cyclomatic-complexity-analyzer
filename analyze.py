
import sys

from frontend.cpp.cfg_builder import CFGBuilder
from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_paths
from visualization.cfg_renderer import render_cfg


def analyze_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        code = file.read()

    cfg = CFGBuilder().build(code)
    result = calculate_complexity(cfg)
    paths = find_independent_paths(cfg)

    print("\n=== Cyclomatic Complexity Analysis ===")
    print("Source file:", filename)
    print("Nodes:", result["nodes"])
    print("Edges:", result["edges"])
    print("Cyclomatic Complexity:", result["complexity"])

    print("\n=== Independent Paths ===")
    for index, path in enumerate(paths, start=1):
        print(f"Path {index}:")
        print(" -> ".join(path))

    render_cfg(cfg, "output/cfg_graph")

    print("\nCFG saved to output/cfg_graph.png")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <source.cpp>")
        raise SystemExit(1)

    analyze_file(sys.argv[1])
