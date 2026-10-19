
from dataclasses import dataclass, field

from tree_sitter import Language, Parser
import tree_sitter_cpp as tscpp


@dataclass
class Node:
    id: int
    label: str


@dataclass
class CFG:
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)


class CFGBuilder:
    def __init__(self):
        self.parser = Parser(Language(tscpp.language()))
        self.cfg = CFG()
        self.next_id = 1
        self.exit_node = None
        self.loop_stack = []

    def add_node(self, label):
        node_id = self.next_id
        self.next_id += 1
        self.cfg.nodes.append(Node(node_id, label))
        return node_id

    def add_edge(self, source, target, label=""):
        edge = (source, target, label)
        if edge not in self.cfg.edges:
            self.cfg.edges.append(edge)

    @staticmethod
    def text(node, source):
        return source[node.start_byte:node.end_byte].decode(
            "utf-8"
        ).strip() if node is not None else ""

    def build(self, code):
        source = code.encode("utf-8")
        tree = self.parser.parse(source)

        self.cfg = CFG()
        self.next_id = 1
        self.loop_stack = []

        if tree.root_node.has_error:
            raise ValueError("C++ source contains syntax errors")

        functions = [
            child for child in tree.root_node.named_children
            if child.type == "function_definition"
        ]

        if not functions:
            raise ValueError("No function definition found")

        entry = self.add_node("Entry")
        self.exit_node = self.add_node("Exit")

        body = functions[0].child_by_field_name("body")
        tails = self.process_block(body, [entry], source)

        for tail in tails:
            self.add_edge(tail, self.exit_node)

        return self.cfg

    # ---------------------------------------------------------
    # Statement blocks
    # ---------------------------------------------------------

    def process_block(self, block, incoming, source):
        if block is None:
            return incoming

        tails = incoming

        for statement in block.named_children:
            if not tails:
                break

            kind = statement.type

            if kind == "if_statement":
                tails = self.process_if(statement, tails, source)

            elif kind == "while_statement":
                tails = self.process_while(statement, tails, source)

            elif kind == "for_statement":
                tails = self.process_for(statement, tails, source)

            elif kind == "return_statement":
                node_id = self.add_node(self.text(statement, source))
                for tail in tails:
                    self.add_edge(tail, node_id)
                self.add_edge(node_id, self.exit_node)
                tails = []

            elif kind == "break_statement":
                node_id = self.add_node("break;")
                for tail in tails:
                    self.add_edge(tail, node_id)

                if self.loop_stack:
                    self.add_edge(
                        node_id, self.loop_stack[-1]["break_target"]
                    )
                tails = []

            elif kind == "continue_statement":
                node_id = self.add_node("continue;")
                for tail in tails:
                    self.add_edge(tail, node_id)

                if self.loop_stack:
                    target = self.loop_stack[-1]["continue_target"]
                    if target is not None:
                        self.add_edge(node_id, target)
                tails = []

            elif kind == "compound_statement":
                tails = self.process_block(statement, tails, source)

            else:
                node_id = self.add_node(self.text(statement, source))
                for tail in tails:
                    self.add_edge(tail, node_id)
                tails = [node_id]

        return tails

    # ---------------------------------------------------------
    # Boolean condition builder
    # Connect each atomic condition to explicit true/false
    # destinations. Handles &&, ||, and parentheses.
    # ---------------------------------------------------------

    def unwrap_condition(self, node):
        while node is not None and node.type in (
            "condition_clause",
            "parenthesized_expression",
        ):
            children = node.named_children
            if not children:
                break
            node = children[0]
        return node

    def build_condition(self, node, incoming, true_target, false_target, source):
        node = self.unwrap_condition(node)

        if node is None:
            for tail in incoming:
                self.add_edge(tail, true_target, "True")
            return

        if node.type == "binary_expression":
            operator = next(
                (
                    child.type
                    for child in node.children
                    if child.type in ("&&", "||")
                ),
                None,
            )

            operands = node.named_children

            if operator and len(operands) >= 2:
                left, right = operands[0], operands[-1]

                if operator == "&&":
                    # If left is true, evaluate right.
                    right_entry = self.add_node("AND next")
                    self.build_condition(
                        left, incoming, right_entry, false_target, source
                    )
                    self.build_condition(
                        right, [right_entry], true_target, false_target, source
                    )
                else:
                    # If left is false, evaluate right.
                    right_entry = self.add_node("OR next")
                    self.build_condition(
                        left, incoming, true_target, right_entry, source
                    )
                    self.build_condition(
                        right, [right_entry], true_target, false_target, source
                    )
                return

        # Atomic decision node.
        decision = self.add_node(self.text(node, source))
        for tail in incoming:
            self.add_edge(tail, decision)
        self.add_edge(decision, true_target, "True")
        self.add_edge(decision, false_target, "False")

    # ---------------------------------------------------------
    # If / else
    # ---------------------------------------------------------

    def process_if(self, statement, incoming, source):
        condition = statement.child_by_field_name("condition")
        consequence = statement.child_by_field_name("consequence")
        alternative = statement.child_by_field_name("alternative")

        true_gate = self.add_node("True branch")
        false_gate = self.add_node("False branch")

        self.build_condition(
            condition, incoming, true_gate, false_gate, source
        )

        true_tails = self.process_block(
            consequence, [true_gate], source
        )

        if alternative is not None:
            else_block = alternative
            if alternative.type == "else_clause":
                else_block = next(
                    (
                        child for child in alternative.named_children
                        if child.type in (
                            "compound_statement",
                            "if_statement",
                        )
                    ),
                    None,
                )
            false_tails = self.process_block(
                else_block, [false_gate], source
            )
        else:
            false_tails = [false_gate]

        return true_tails + false_tails

    # ---------------------------------------------------------
    # While loop
    # ---------------------------------------------------------

    def process_while(self, statement, incoming, source):
        condition = statement.child_by_field_name("condition")
        body = statement.child_by_field_name("body")

        condition_entry = self.add_node("While condition")
        after_loop = self.add_node("After while")

        for tail in incoming:
            self.add_edge(tail, condition_entry)

        body_entry = self.add_node("While body")
        self.build_condition(
            condition, [condition_entry], body_entry, after_loop, source
        )

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })

        body_tails = self.process_block(body, [body_entry], source)

        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry, "Back")

        return [after_loop]

    # ---------------------------------------------------------
    # For loop
    # ---------------------------------------------------------

    def process_for(self, statement, incoming, source):
        initializer = statement.child_by_field_name("initializer")
        condition = statement.child_by_field_name("condition")
        update = statement.child_by_field_name("update")
        body = statement.child_by_field_name("body")

        tails = incoming

        if initializer is not None:
            init_id = self.add_node(self.text(initializer, source))
            for tail in tails:
                self.add_edge(tail, init_id)
            tails = [init_id]

        condition_entry = self.add_node("For condition")
        for tail in tails:
            self.add_edge(tail, condition_entry)

        after_loop = self.add_node("After for")
        body_entry = self.add_node("For body")

        if condition is not None:
            self.build_condition(
                condition, [condition_entry], body_entry, after_loop, source
            )
        else:
            self.add_edge(condition_entry, body_entry, "True")

        update_id = None
        if update is not None:
            update_id = self.add_node(self.text(update, source))

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": (
                update_id if update_id is not None else condition_entry
            ),
        })

        body_tails = self.process_block(body, [body_entry], source)

        self.loop_stack.pop()

        if update_id is not None:
            for tail in body_tails:
                self.add_edge(tail, update_id)
            self.add_edge(update_id, condition_entry, "Back")
        else:
            for tail in body_tails:
                self.add_edge(tail, condition_entry, "Back")

        return [after_loop]


if __name__ == "__main__":
    code = """
    int main() {
        int x = 5;
        int y = 10;

        if (x > 0 && y > 0) {
            x++;
        }

        if (x > 0 || y < 0) {
            y++;
        }

        return 0;
    }
    """

    cfg = CFGBuilder().build(code)

    print("NODES")
    for node in cfg.nodes:
        print(f"{node.id}: {node.label}")

    print("\\nEDGES")
    for source, target, label in cfg.edges:
        print(f"{source} -> {target} [{label}]")
