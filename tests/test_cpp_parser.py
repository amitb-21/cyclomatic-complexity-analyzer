import shutil

import pytest

from engine.complexity import calculate_complexity
from engine.independent_paths import find_independent_paths
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

    def test_multiple_functions_are_included_in_file_complexity(self, parser, tmp_path):
        code = """
        int first(int x) {
            if (x > 0) return 1;
            return 0;
        }
        int second(int x) {
            while (x > 0) x--;
            return x;
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))

        assert calculate_complexity(cfg)["complexity"] == 4
        assert any(label.startswith("function:") for label in cfg.edge_labels.values())

    def test_switch_break_targets_switch_inside_loop(self, parser, tmp_path):
        code = """
        int run(int x) {
            while (x > 0) {
                switch (x) {
                    case 1: break;
                    default: x--;
                }
                x--;
            }
            return x;
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))
        after_switch = next(
            node for node in cfg.nodes.values()
            if node.label == "After switch"
        )
        break_node = next(
            node for node in cfg.nodes.values()
            if node.label == "break;"
        )
        after_loop = next(
            node for node in cfg.nodes.values()
            if node.label == "After while"
        )
        loop_condition_entry = next(
            node for node in cfg.nodes.values()
            if node.label == "While condition"
        )
        condition_decision = next(
            node for node in cfg.nodes.values()
            if node.label == "x > 0"
        )
        post_switch_statement = after_switch.successors[0]

        assert break_node.successors == [after_switch]
        assert post_switch_statement.label == "x--;"
        assert post_switch_statement.successors == [loop_condition_entry]
        assert condition_decision in loop_condition_entry.successors
        assert after_loop in condition_decision.successors

    def test_forward_goto_connects_to_labeled_statement(self, parser, tmp_path):
        code = """
        int run(int value) {
            if (value < 0) {
                goto finish;
            }
            value++;
        finish:
            return value;
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))
        goto = next(node for node in cfg.nodes.values() if node.label == "goto finish;")
        label = next(node for node in cfg.nodes.values() if node.label == "Label finish")
        returned = next(node for node in cfg.nodes.values() if node.label == "return value;")

        assert goto.successors == [label]
        assert returned in label.successors
        assert calculate_complexity(cfg)["complexity"] == 2
        assert len(find_independent_paths(cfg)) == 2

    def test_backward_goto_creates_a_control_flow_cycle(self, parser, tmp_path):
        code = """
        int run(int value) {
        again:
            if (value > 0) {
                value--;
                goto again;
            }
            return value;
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))
        goto = next(node for node in cfg.nodes.values() if node.label == "goto again;")
        label = next(node for node in cfg.nodes.values() if node.label == "Label again")

        assert goto.successors == [label]
        assert calculate_complexity(cfg)["complexity"] == 2
        assert len(find_independent_paths(cfg)) == 2

    def test_goto_reaches_label_nested_in_unreachable_block(self, parser, tmp_path):
        code = """
        int run(int value) {
            goto nested;
            if (value > 0) {
            nested:
                return value;
            }
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))
        goto = next(node for node in cfg.nodes.values() if node.label == "goto nested;")
        label = next(node for node in cfg.nodes.values() if node.label == "Label nested")
        returned = next(node for node in cfg.nodes.values() if node.label == "return value;")

        assert goto.successors == [label]
        assert label.successors == [returned]

    def test_lambda_labels_are_not_function_goto_targets(self, parser, tmp_path):
        code = """
        int run() {
            auto callback = []() {
            local:
                return 0;
            };
            return callback();
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))

        assert not any(node.label == "Label local" for node in cfg.nodes.values())
        assert calculate_complexity(cfg)["complexity"] == 1

    @pytest.mark.parametrize(
        ("source", "message"),
        [
            ("int run() { goto missing; }", "goto target label"),
            (
                "int run() { same: return 0; same: return 1; }",
                "Duplicate C\\+\\+ label: same",
            ),
        ],
    )
    def test_goto_label_errors_are_reported(self, parser, tmp_path, source, message):
        with pytest.raises(ValueError, match=message):
            parser.build_cfg(write_temp_cpp(tmp_path, source))

    @pytest.mark.skipif(
        not any(shutil.which(name) for name in ("g++", "clang++", "c++")),
        reason="GCC or Clang is required to test C++ macro preprocessing",
    )
    def test_macro_expansion_and_included_header_macros(self, parser, tmp_path):
        (tmp_path / "analysis_macros.h").write_text(
            "#define IS_NEGATIVE(value) ((value) < 0)\n"
            "#define LIMIT 10\n",
            encoding="utf-8",
        )
        code = """
        #include "analysis_macros.h"
        int run(int value) {
            if (IS_NEGATIVE(value)) {
                return -1;
            }
            if (value > LIMIT) {
                return 1;
            }
            return 0;
        }
        """
        cfg = parser.build_cfg(write_temp_cpp(tmp_path, code))

        assert calculate_complexity(cfg)["complexity"] == 3
        assert any(node.label == "(value) < 0" for node in cfg.nodes.values())
        assert len(find_independent_paths(cfg)) == 3