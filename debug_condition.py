
from tree_sitter import Language, Parser
import tree_sitter_cpp as tscpp

code = """
int main() {
    int x = 5;
    int y = 10;
    if (x > 0 && y > 0) {
        x++;
    }
    return 0;
}
"""

parser = Parser(Language(tscpp.language()))
tree = parser.parse(code.encode("utf-8"))


def print_tree(node, source, depth=0):
    text = source[node.start_byte:node.end_byte].decode("utf-8")
    print("  " * depth + f"{node.type}: {text.strip()!r}")

    for child in node.children:
        print_tree(child, source, depth + 1)


print_tree(tree.root_node, code.encode("utf-8"))
