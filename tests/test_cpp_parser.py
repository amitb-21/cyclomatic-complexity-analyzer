import pytest
from frontend.cpp.parser import CppParser

@pytest.fixture
def parser():
    """Provides a reusable CppParser instance for the tests."""
    return CppParser()

def write_temp_cpp(tmp_path, code: str) -> str:
    """Helper to write a C++ snippet to a temporary file and return the path."""
    test_file = tmp_path / "test_snippet.cpp"
    test_file.write_text(code, encoding="utf-8")
    return str(test_file)

class TestCppParser:

    def test_sequential_statements(self, parser, tmp_path):
        """Tests that basic linear statements create a straight-line CFG."""
        code = """
        int main() {
            int x = 10;
            int y = 20;
            return 0;
        }
        """
        file_path = write_temp_cpp(tmp_path, code)
        cfg = parser.build_cfg(file_path)
        
        # Nodes: Entry, int x = 10;, int y = 20;, return 0;, Exit
        assert len(cfg.nodes) == 5, f"Expected 5 nodes, got {len(cfg.nodes)}"
        
        edges = cfg.get_edges()
        # Edges: Entry->x, x->y, y->return, return->Exit
        assert len(edges) == 4, f"Expected 4 edges, got {len(edges)}"

    def test_if_else_branching(self, parser, tmp_path):
        """Tests that an if/else block properly splits and merges."""
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
        file_path = write_temp_cpp(tmp_path, code)
        cfg = parser.build_cfg(file_path)
        
        # Verify that the graph branches out. We expect at least one node to have multiple successors.
        branch_nodes = [node for node in cfg.nodes.values() if len(node.successors) > 1]
        assert len(branch_nodes) >= 1, "Graph should contain at least one branch node for the 'if' condition."
        
        # The true branch and false branch should eventually merge back (or both hit the return/exit)
        edges = cfg.get_edges()
        assert len(edges) > 5, "Graph should have sufficient edges to represent the if-else fork and merge."

    def test_while_loop_cycle(self, parser, tmp_path):
        """Tests that a while loop creates a backward edge (cycle)."""
        code = """
        int main() {
            int x = 5;
            while (x > 0) {
                x--;
            }
            return 0;
        }
        """
        file_path = write_temp_cpp(tmp_path, code)
        cfg = parser.build_cfg(file_path)
        
        edges = cfg.get_edges()
        
        # Ensure there are enough nodes for condition, body, and exit.
        assert len(cfg.nodes) >= 6, "Graph should contain nodes for loop condition, body, and exit."
        
        branch_nodes = [node for node in cfg.nodes.values() if len(node.successors) > 1]
        assert len(branch_nodes) >= 1, "The while condition must have multiple successors."

    def test_do_while_loop_runs_body_before_condition(self, parser, tmp_path):
        code = """
        int main() {
            int x = 0;
            do {
                x++;
            } while (x < 3);
            return 0;
        }
        """
        file_path = write_temp_cpp(tmp_path, code)
        cfg = parser.build_cfg(file_path)

        body_entry = next(
            node for node in cfg.nodes.values()
            if node.label == "Do-while body"
        )
        condition_entry = next(
            node for node in cfg.nodes.values()
            if node.label == "Do-while condition"
        )
        condition_decision = condition_entry.successors[0]
        after_loop = next(
            node for node in cfg.nodes.values()
            if node.label == "After do-while"
        )
        body_statement = body_entry.successors[0]
        initializer = cfg.start_node.successors[0]

        assert body_entry in initializer.successors
        assert condition_entry in body_statement.successors
        assert set(condition_decision.successors) == {body_entry, after_loop}

    def test_switch_dispatch_break_and_fallthrough(self, parser, tmp_path):
        code = """
        int main() {
            int x = 1;
            switch (x) {
                case 0:
                    x++;
                    break;
                case 1:
                    x--;
                default:
                    x = 2;
            }
            return 0;
        }
        """
        file_path = write_temp_cpp(tmp_path, code)
        cfg = parser.build_cfg(file_path)

        selector = next(
            node for node in cfg.nodes.values()
            if node.label.startswith("Switch ")
        )
        case_one = next(
            (
                node for node in cfg.nodes.values()
                if node.label == "Case 1"
            ),
            None,
        )
        assert case_one is not None, [node.label for node in cfg.nodes.values()]
        default = next(
            node for node in cfg.nodes.values()
            if node.label == "Default"
        )
        decrement = next(
            node for node in cfg.nodes.values()
            if node.label == "x--;"
        )
        break_node = next(
            node for node in cfg.nodes.values()
            if node.label == "break;"
        )
        after_switch = next(
            node for node in cfg.nodes.values()
            if node.label == "After switch"
        )

        assert len(selector.successors) == 3
        assert case_one in selector.successors
        assert default in decrement.successors
        assert break_node.successors == [after_switch]

    def test_syntax_error_handling(self, parser, tmp_path):
        """Tests that the parser raises an error on invalid C++ code."""
        code = """
        int main() {
            int x = 10  // Missing semicolon
            if (x > 0) {
        } // Missing closing brace for main
        """
        file_path = write_temp_cpp(tmp_path, code)
        
        with pytest.raises(ValueError, match=r"C\+\+ source contains syntax errors"):
            parser.build_cfg(file_path)