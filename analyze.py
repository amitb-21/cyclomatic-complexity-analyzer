import os
import sys

# Import the C++ parser
from frontend.cpp.parser import CppParser

# Import the language-agnostic math engine components
from engine.complexity import calculate_complexity

# PYLANCE FIX NOTE: If "calculate_independent_paths" is still underlined, 
# open engine/independent_paths.py and check the exact name of the function 
# that calculates the paths (e.g., it might be get_independent_paths or find_paths).
# Update the imported name below to match it exactly.
import importlib

independent_paths = importlib.import_module("engine.independent_paths")

from visualization.cfg_renderer import render_cfg

def get_parser_for_file(file_path: str):
    """Routes the file to the appropriate parser based on its extension."""
    _, extension = os.path.splitext(file_path.lower())
    
    if extension in ['.cpp', '.cc', '.c', '.hpp', '.h']:
        return CppParser()
    elif extension == '.py':
        raise NotImplementedError("Python support is planned but not yet implemented.")
    elif extension == '.java':
        raise NotImplementedError("Java support is planned but not yet implemented.")
    else:
        raise ValueError(f"Unsupported file format: {extension}")

def main(file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    try:
        # 1. Route to the correct parser
        parser = get_parser_for_file(file_path)
        
        # 2. Parse the code to generate the standardized CFG
        # PYLANCE FIX NOTE: To fix the "Cannot access attribute 'build_cfg'" error,
        # you MUST update frontend/cpp/parser.py so that the CppParser class 
        # inherits from BaseParser and defines the build_cfg(self, file_path) method.
        cfg = getattr(parser, "build_cfg")(file_path)
        
        # 3. Feed the CFG into the math engine
        complexity = calculate_complexity(cfg)
        path_calculator = next(
            (
                getattr(independent_paths, name)
                for name in (
                    "calculate_independent_paths",
                    "get_independent_paths",
                    "find_paths",
                )
                if hasattr(independent_paths, name)
            ),
            None,
        )
        if path_calculator is None:
            raise ImportError("No independent-path calculation function found.")
        paths = path_calculator(cfg)
        
        # 4. Output the results
        print(f"\n--- Analysis for {os.path.basename(file_path)} ---")
        print(f"Cyclomatic Complexity: {complexity}")
        print(f"Total Independent Paths: {len(paths)}")
        for idx, path in enumerate(paths, 1):
            print(f"  Path {idx}: {path}")
            
        # 5. Generate the graph visualization
        # PYLANCE FIX: Removed the incorrect "output_filename=" keyword. 
        # Passing the parameter positionally instead.
        render_cfg(cfg, f"{os.path.basename(file_path)}_cfg")
        print("\nCFG visualization generated successfully.")
        
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <path_to_source_file>")
        sys.exit(1)
        
    main(sys.argv[1])