
from tree_sitter import Language, Parser
import tree_sitter_cpp as tscpp


class CppParser:
    def __init__(self):
        language = Language(tscpp.language())
        self.parser = Parser(language)

    def parse(self, source_code: str):
        return self.parser.parse(source_code.encode("utf-8"))


def print_tree(node, source_bytes, indent=0):
    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
    print("  " * indent + f"{node.type}: {text[:70]!r}")

    for child in node.children:
        print_tree(child, source_bytes, indent + 1)


if __name__ == "__main__":
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

    parser = CppParser()
    tree = parser.parse(code)
    print_tree(tree.root_node, code.encode("utf-8"))
