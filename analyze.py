import os
import sys

from frontend.cpp.parser import CppParser
from frontend.python.parser import PythonParser
from frontend.java import JavaParser

from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_paths
from visualization.cfg_renderer import render_cfg


def get_parser_for_file(file_path: str):
    """Select the parser based on the source file extension."""
    _, extension = os.path.splitext(file_path.lower())

    if extension in (".cpp", ".cc", ".c", ".hpp", ".h"):
        return CppParser()

    if extension == ".py":
        return PythonParser()

    if extension == ".java":
        return JavaParser()

    raise ValueError(f"Unsupported file format: {extension}")


def main(file_path: str) -> None:
    """Analyze source code and generate a control-flow graph."""
    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    try:
        # 1. Select the correct language parser.
        parser = get_parser_for_file(file_path)

        # 2. Build the standardized CFG.
        cfg = parser.build_cfg(file_path)

        # 3. Calculate cyclomatic complexity.
        complexity_result = calculate_complexity(cfg)
        complexity = (
            complexity_result["complexity"]
            if isinstance(complexity_result, dict)
            else complexity_result
        )

        # 4. Calculate independent paths using your actual function.
        paths = find_independent_paths(cfg)

        # 5. Display the results.
        print(f"\n--- Analysis for {os.path.basename(file_path)} ---")
        print(f"Cyclomatic Complexity: {complexity}")
        print(f"Total Independent Paths: {len(paths)}")

        for index, path in enumerate(paths, start=1):
            print(f"  Path {index}: {' -> '.join(map(str, path))}")

        # 6. Generate the CFG visualization.
        output_name = f"{os.path.basename(file_path)}_cfg"
        render_cfg(cfg, output_name)

        print("\nCFG visualization generated successfully.")

    except Exception as error:
        print(f"Error analyzing {file_path}: {error}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <path_to_source_file>")
        sys.exit(1)

    main(sys.argv[1])
