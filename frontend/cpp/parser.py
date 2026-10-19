import os
import re
import shlex
import shutil
import subprocess
from tree_sitter import Language, Parser
import tree_sitter_cpp as tscpp

# Import the standardized interfaces
from frontend.base_parser import BaseParser, CFG

from frontend.cpp.cfg_builder import build_cpp_cfg

class CppParser(BaseParser):
    _LINE_MARKER = re.compile(r'^#\s+\d+\s+"((?:\\.|[^"])*)"')
    _PREPROCESSOR_DIRECTIVE = re.compile(
        rb"^[ \t]*#[ \t]*[A-Za-z]",
        re.MULTILINE,
    )

    def __init__(self):
        language = Language(tscpp.language())
        self.parser = Parser(language)

    @staticmethod
    def _find_preprocessor() -> list[str] | None:
        configured = os.environ.get("CXX")
        candidates = (
            [
                [
                    argument.strip('"')
                    for argument in shlex.split(
                        configured,
                        posix=os.name != "nt",
                    )
                ]
            ]
            if configured
            else []
        )
        candidates.extend(([name] for name in ("g++", "clang++", "c++")))

        for candidate in candidates:
            if candidate:
                executable = shutil.which(candidate[0])
                if executable:
                    return [executable, *candidate[1:]]
        return None

    @staticmethod
    def _same_path(first: str, second: str) -> bool:
        return os.path.normcase(os.path.realpath(first)) == os.path.normcase(
            os.path.realpath(second)
        )

    def _preprocess(self, file_path: str, source_code: bytes) -> bytes:
        if not self._PREPROCESSOR_DIRECTIVE.search(source_code):
            return source_code

        compiler = self._find_preprocessor()
        if compiler is None:
            raise ValueError(
                "C++ source contains preprocessor directives, but no GCC or "
                "Clang preprocessor was found. Install one or remove the "
                "preprocessor directives."
            )

        absolute_path = os.path.abspath(file_path)
        source_directory = os.path.dirname(absolute_path)
        command = [
            *compiler,
            "-E",
            "-x",
            "c++",
            "-I",
            source_directory,
            absolute_path,
        ]

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=30,
                cwd=source_directory or None,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError(
                "C++ preprocessing exceeded the 30-second limit"
            ) from error
        except OSError as error:
            raise ValueError(
                f"Could not run the C++ preprocessor: {error}"
            ) from error

        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(
                "C++ preprocessing failed"
                + (f": {detail}" if detail else ".")
            )

        active_file = None
        main_file_lines = []
        for line in result.stdout.splitlines():
            marker = self._LINE_MARKER.match(
                line.decode("utf-8", errors="replace")
            )
            if marker:
                active_file = marker.group(1)
                continue
            if active_file and self._same_path(active_file, absolute_path):
                main_file_lines.append(line)

        if not main_file_lines:
            raise ValueError(
                "C++ preprocessing produced no source lines for the input file."
            )

        return b"\n".join(main_file_lines) + b"\n"

    def parse(self, file_path: str):
        """Preprocess directives when needed, then return the Tree-sitter AST."""
        with open(file_path, "rb") as source_file:
            source_code = source_file.read()
        return self.parser.parse(self._preprocess(file_path, source_code))

    def build_cfg(self, file_path: str) -> CFG:
        """
        Parses the C++ file and delegates to the CFG builder 
        to construct the standardized CFG.
        """
        with open(file_path, "rb") as source_file:
            source_bytes = source_file.read()
        source_bytes = self._preprocess(file_path, source_bytes)
        tree = self.parser.parse(source_bytes)

        return build_cpp_cfg(tree.root_node, source_bytes)


def print_tree(node, source_bytes, indent=0):
    """Helper function to print the Tree-sitter AST for debugging."""
    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
    print("  " * indent + f"{node.type}: {text[:70]!r}")

    for child in node.children:
        print_tree(child, source_bytes, indent + 1)


if __name__ == "__main__":
    # Quick local test script to verify Tree-sitter parsing
    code = """
    int main() {
        int x = 10;
        if (x > 0) {
            x++;
        } else {
            x--;
        }
        return 0;
    }
    """
    
    # Write to a temporary file to test the BaseParser file_path interface
    test_filename = "temp_test_code.cpp"
    with open(test_filename, "w", encoding="utf-8") as f:
        f.write(code)
        
    try:
        parser = CppParser()
        tree = parser.parse(test_filename)
        
        with open(test_filename, "rb") as f:
            source_bytes = f.read()
            
        print("--- Tree-sitter AST ---")
        print_tree(tree.root_node, source_bytes)
        
    finally:
        # Clean up the temporary file
        if os.path.exists(test_filename):
            os.remove(test_filename)