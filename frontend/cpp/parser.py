import os
from tree_sitter import Language, Parser
import tree_sitter_cpp as tscpp

# Import the standardized interfaces
from frontend.base_parser import BaseParser, CFG

# Import your CFG builder logic
# (We will need to update cfg_builder.py next to accept the tree_sitter node)
from frontend.cpp.cfg_builder import build_cpp_cfg

class CppParser(BaseParser):
    def __init__(self):
        language = Language(tscpp.language())
        self.parser = Parser(language)

    def parse(self, file_path: str):
        """Reads the source file and returns the Tree-sitter AST."""
        with open(file_path, 'rb') as f:
            source_code = f.read()
        return self.parser.parse(source_code)

    def build_cfg(self, file_path: str) -> CFG:
        """
        Parses the C++ file and delegates to the CFG builder 
        to construct the standardized CFG.
        """
        # 1. Parse the file to get the Tree-sitter tree
        tree = self.parse(file_path)
        
        # 2. Read the source bytes (Tree-sitter needs this to extract code text)
        with open(file_path, 'rb') as f:
            source_bytes = f.read()
            
        # 3. Build and return the standardized CFG
        # We pass both the root node and the raw bytes to the builder
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