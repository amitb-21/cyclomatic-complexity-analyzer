from typing import Optional
from frontend.base_parser import CFG, CFGNode

class CppCFGBuilder:
    def __init__(self, source_bytes: bytes):
        self.cfg = CFG()
        self.next_id = 1
        self.exit_node = None
        self.loop_stack = []
        self.source_bytes = source_bytes

    def add_node(self, label: str) -> CFGNode:
        """Creates a standardized CFGNode, adds it to the graph, and returns the object."""
        node = CFGNode(self.next_id, label)
        self.cfg.add_node(node)
        self.next_id += 1
        return node

    def add_edge(self, source: Optional[CFGNode], target: Optional[CFGNode], label: str = ""):
        """Links two nodes together. Safely ignores None values."""
        if source is not None and target is not None:
            self.cfg.add_edge(source, target, label)

    def text(self, node) -> str:
        """Extracts the raw string from the source bytes."""
        if node is None:
            return ""
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8").strip()

    def build(self, root_node) -> CFG:
        """Main entry point to begin traversing the Tree-sitter AST."""
        if root_node.has_error:
            raise ValueError("C++ source contains syntax errors")

        # Extract function definitions
        functions = [
            child for child in root_node.named_children
            if child.type == "function_definition"
        ]

        if not functions:
            raise ValueError("No function definition found")

        # Initialize Standardized Entry and Exit points
        entry = self.add_node("Entry")
        self.exit_node = self.add_node("Exit")
        
        self.cfg.start_node = entry
        self.cfg.end_node = self.exit_node

        body = functions[0].child_by_field_name("body")
        tails = self.process_block(body, [entry])

        for tail in tails:
            self.add_edge(tail, self.exit_node)

        return self.cfg

    # ---------------------------------------------------------
    # Statement blocks
    # ---------------------------------------------------------

    def process_block(self, block, incoming: list[CFGNode]) -> list[CFGNode]:
        if block is None:
            return incoming

        statements = (
            block.named_children
            if block.type == "compound_statement"
            else [block]
        )
        return self.process_statements(statements, incoming)

    def process_statements(self, statements, incoming: list[CFGNode]) -> list[CFGNode]:
        tails = incoming

        for statement in statements:
            if not tails:
                break

            kind = statement.type

            if kind == "if_statement":
                tails = self.process_if(statement, tails)

            elif kind == "while_statement":
                tails = self.process_while(statement, tails)

            elif kind == "do_statement":
                tails = self.process_do_while(statement, tails)

            elif kind == "for_statement":
                tails = self.process_for(statement, tails)

            elif kind == "switch_statement":
                tails = self.process_switch(statement, tails)

            elif kind == "return_statement":
                ret_node = self.add_node(self.text(statement))
                for tail in tails:
                    self.add_edge(tail, ret_node)
                self.add_edge(ret_node, self.exit_node)
                tails = []

            elif kind == "break_statement":
                brk_node = self.add_node("break;")
                for tail in tails:
                    self.add_edge(tail, brk_node)

                if self.loop_stack:
                    self.add_edge(brk_node, self.loop_stack[-1]["break_target"])
                tails = []

            elif kind == "continue_statement":
                cont_node = self.add_node("continue;")
                for tail in tails:
                    self.add_edge(tail, cont_node)

                if self.loop_stack:
                    target = self.loop_stack[-1]["continue_target"]
                    if target is not None:
                        self.add_edge(cont_node, target)
                tails = []

            elif kind == "compound_statement":
                tails = self.process_block(statement, tails)

            else:
                stmt_node = self.add_node(self.text(statement))
                for tail in tails:
                    self.add_edge(tail, stmt_node)
                tails = [stmt_node]

        return tails

    # ---------------------------------------------------------
    # Boolean condition builder
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

    def build_condition(self, node, incoming: list[CFGNode], true_target: CFGNode, false_target: CFGNode):
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
                    right_entry = self.add_node("AND next")
                    self.build_condition(left, incoming, right_entry, false_target)
                    self.build_condition(right, [right_entry], true_target, false_target)
                else:
                    right_entry = self.add_node("OR next")
                    self.build_condition(left, incoming, true_target, right_entry)
                    self.build_condition(right, [right_entry], true_target, false_target)
                return

        # Atomic decision node
        decision = self.add_node(self.text(node))
        for tail in incoming:
            self.add_edge(tail, decision)
        self.add_edge(decision, true_target, "True")
        self.add_edge(decision, false_target, "False")

    # ---------------------------------------------------------
    # If / else
    # ---------------------------------------------------------

    def process_if(self, statement, incoming: list[CFGNode]):
        condition = statement.child_by_field_name("condition")
        consequence = statement.child_by_field_name("consequence")
        alternative = statement.child_by_field_name("alternative")

        true_gate = self.add_node("True branch")
        false_gate = self.add_node("False branch")

        self.build_condition(condition, incoming, true_gate, false_gate)

        true_tails = self.process_block(consequence, [true_gate])

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
            false_tails = self.process_block(else_block, [false_gate])
        else:
            false_tails = [false_gate]

        return true_tails + false_tails

    # ---------------------------------------------------------
    # While loop
    # ---------------------------------------------------------

    def process_while(self, statement, incoming: list[CFGNode]):
        condition = statement.child_by_field_name("condition")
        body = statement.child_by_field_name("body")

        condition_entry = self.add_node("While condition")
        after_loop = self.add_node("After while")

        for tail in incoming:
            self.add_edge(tail, condition_entry)

        body_entry = self.add_node("While body")
        self.build_condition(condition, [condition_entry], body_entry, after_loop)

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })

        body_tails = self.process_block(body, [body_entry])

        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry, "Back")

        return [after_loop]

    def process_do_while(self, statement, incoming: list[CFGNode]):
        body = statement.child_by_field_name("body")
        condition = statement.child_by_field_name("condition")

        body_entry = self.add_node("Do-while body")
        condition_entry = self.add_node("Do-while condition")
        after_loop = self.add_node("After do-while")

        for tail in incoming:
            self.add_edge(tail, body_entry)

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })
        body_tails = self.process_block(body, [body_entry])
        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry)

        self.build_condition(
            condition,
            [condition_entry],
            body_entry,
            after_loop,
        )
        return [after_loop]

    def process_switch(self, statement, incoming: list[CFGNode]):
        condition = statement.child_by_field_name("condition")
        body = statement.child_by_field_name("body")
        body_statements = (
            body.named_children
            if body is not None and body.type == "compound_statement"
            else [body] if body is not None else []
        )
        cases = [
            child for child in body_statements
            if child.type == "case_statement"
        ]

        selector = self.add_node(f"Switch {self.text(condition)}")
        after_switch = self.add_node("After switch")
        for tail in incoming:
            self.add_edge(tail, selector)

        case_entries = []
        has_default = False
        for case in cases:
            value = case.child_by_field_name("value")
            is_default = value is None
            has_default = has_default or is_default
            label = "Default" if is_default else f"Case {self.text(value)}"
            case_entry = self.add_node(label)
            self.add_edge(selector, case_entry, label)

            statements = [
                child for child in case.named_children
                if value is None
                or (child.start_byte, child.end_byte)
                != (value.start_byte, value.end_byte)
            ]
            case_entries.append((case_entry, statements))

        if not has_default:
            self.add_edge(selector, after_switch, "No matching case")

        continue_target = next(
            (
                context["continue_target"]
                for context in reversed(self.loop_stack)
                if context["continue_target"] is not None
            ),
            None,
        )
        self.loop_stack.append({
            "break_target": after_switch,
            "continue_target": continue_target,
        })

        fallthrough_tails = []
        for case_entry, case_statements in case_entries:
            for tail in fallthrough_tails:
                self.add_edge(tail, case_entry)
            fallthrough_tails = self.process_statements(
                case_statements,
                [case_entry],
            )

        self.loop_stack.pop()

        for tail in fallthrough_tails:
            self.add_edge(tail, after_switch)

        return [after_switch]

    # ---------------------------------------------------------
    # For loop
    # ---------------------------------------------------------

    def process_for(self, statement, incoming: list[CFGNode]):
        initializer = statement.child_by_field_name("initializer")
        condition = statement.child_by_field_name("condition")
        update = statement.child_by_field_name("update")
        body = statement.child_by_field_name("body")

        tails = incoming

        if initializer is not None:
            init_node = self.add_node(self.text(initializer))
            for tail in tails:
                self.add_edge(tail, init_node)
            tails = [init_node]

        condition_entry = self.add_node("For condition")
        for tail in tails:
            self.add_edge(tail, condition_entry)

        after_loop = self.add_node("After for")
        body_entry = self.add_node("For body")

        if condition is not None:
            self.build_condition(condition, [condition_entry], body_entry, after_loop)
        else:
            self.add_edge(condition_entry, body_entry, "True")

        update_node = None
        if update is not None:
            update_node = self.add_node(self.text(update))

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": update_node if update_node is not None else condition_entry,
        })

        body_tails = self.process_block(body, [body_entry])

        self.loop_stack.pop()

        if update_node is not None:
            for tail in body_tails:
                self.add_edge(tail, update_node)
            self.add_edge(update_node, condition_entry, "Back")
        else:
            for tail in body_tails:
                self.add_edge(tail, condition_entry, "Back")

        return [after_loop]


def build_cpp_cfg(root_node, source_bytes: bytes) -> CFG:
    """Entry point called by CppParser."""
    builder = CppCFGBuilder(source_bytes)
    return builder.build(root_node)