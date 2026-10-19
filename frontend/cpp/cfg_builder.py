from typing import Optional
from frontend.base_parser import CFG, CFGNode

class CppCFGBuilder:
    def __init__(self, source_bytes: bytes):
        self.cfg = CFG()
        self.next_id = 1
        self.exit_node = None
        self.loop_stack = []
        self.source_bytes = source_bytes
        self.label_nodes: dict[str, CFGNode] = {}
        self.referenced_labels: set[str] = set()
        self.jumped_labels: set[str] = set()
        self.processed_labels: set[str] = set()

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

        # Analyze every function definition in source order, including
        # definitions nested inside namespaces and classes.
        functions = []

        def collect_functions(node):
            if node.type == "function_definition":
                functions.append(node)
            for child in node.named_children:
                collect_functions(child)

        collect_functions(root_node)

        if not functions:
            raise ValueError("No function definition found")

        if len(functions) == 1:
            return self.build_function(functions[0])

        member_cfgs = []
        for function in functions:
            member_builder = CppCFGBuilder(self.source_bytes)
            member_cfgs.append(
                (
                    self.text(function.child_by_field_name("declarator")),
                    member_builder.build_function(function),
                )
            )
        return self.combine_cfgs(member_cfgs)

    def build_function(self, function_node) -> CFG:
        self.label_nodes = {}
        self.referenced_labels = set()
        self.jumped_labels = set()
        self.processed_labels = set()
        body = function_node.child_by_field_name("body")
        self.collect_gotos_and_labels(body)
        missing_labels = sorted(
            self.referenced_labels - self.label_nodes.keys()
        )
        if missing_labels:
            raise ValueError(
                "C++ goto target label(s) not found: "
                + ", ".join(missing_labels)
            )

        # Initialize Standardized Entry and Exit points
        entry = self.add_node("Entry")
        self.exit_node = self.add_node("Exit")
        
        self.cfg.start_node = entry
        self.cfg.end_node = self.exit_node

        tails = self.process_block(body, [entry])

        for tail in tails:
            self.add_edge(tail, self.exit_node)

        return self.cfg

    def collect_gotos_and_labels(self, node) -> None:
        if node is None or node.type == "lambda_expression":
            return

        if node.type == "labeled_statement":
            label_node = node.child_by_field_name("label")
            label = self.text(label_node)
            if not label:
                raise ValueError("C++ labeled statement has an empty label")
            if label in self.label_nodes:
                raise ValueError(f"Duplicate C++ label: {label}")
            self.label_nodes[label] = self.add_node(f"Label {label}")

        elif node.type == "goto_statement":
            label_node = node.child_by_field_name("label")
            label = self.text(label_node)
            if not label:
                raise ValueError("C++ goto statement has no target label")
            self.referenced_labels.add(label)

        for child in node.named_children:
            self.collect_gotos_and_labels(child)

    @staticmethod
    def combine_cfgs(member_cfgs: list[tuple[str, CFG]]) -> CFG:
        combined = CFG()
        entry = CFGNode(1, "Entry")
        exit_node = CFGNode(2, "Exit")
        combined.add_node(entry)
        combined.add_node(exit_node)
        combined.start_node = entry
        combined.end_node = exit_node
        next_id = 3

        for name, member_cfg in member_cfgs:
            id_map = {}
            for old_id, old_node in member_cfg.nodes.items():
                new_node = CFGNode(next_id, old_node.label)
                combined.add_node(new_node)
                id_map[old_id] = new_node
                next_id += 1

            for source_id, target_id in member_cfg.get_edges():
                label = member_cfg.edge_labels.get((source_id, target_id), "")
                combined.add_edge(id_map[source_id], id_map[target_id], label)

            if member_cfg.start_node is not None:
                combined.add_edge(
                    entry,
                    id_map[member_cfg.start_node.node_id],
                    f"function: {name}",
                )
            if member_cfg.end_node is not None:
                combined.add_edge(
                    id_map[member_cfg.end_node.node_id],
                    exit_node,
                )

        return combined

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
                if statement.type != "labeled_statement":
                    self.process_pending_labels(statement)
                    continue
                label = self.text(statement.child_by_field_name("label"))
                if label not in self.jumped_labels:
                    self.process_pending_labels(statement)
                    continue

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

            elif kind == "goto_statement":
                label = self.text(statement.child_by_field_name("label"))
                goto_node = self.add_node(self.text(statement))
                for tail in tails:
                    self.add_edge(tail, goto_node)
                target = self.label_nodes.get(label)
                if target is None:
                    raise ValueError(f"C++ goto target label not found: {label}")
                self.add_edge(goto_node, target, "Goto")
                self.jumped_labels.add(label)
                tails = []

            elif kind == "labeled_statement":
                label_node = statement.child_by_field_name("label")
                label = self.text(label_node)
                if label in self.processed_labels:
                    continue
                self.processed_labels.add(label)
                label_entry = self.label_nodes[label]
                for tail in tails:
                    self.add_edge(tail, label_entry)
                label_span = (
                    label_node.start_byte,
                    label_node.end_byte,
                )
                body = next(
                    (
                        child for child in statement.named_children
                        if (child.start_byte, child.end_byte) != label_span
                    ),
                    None,
                )
                tails = self.process_block(body, [label_entry]) if body else [label_entry]

            elif kind == "compound_statement":
                tails = self.process_block(statement, tails)

            else:
                stmt_node = self.add_node(self.text(statement))
                for tail in tails:
                    self.add_edge(tail, stmt_node)
                tails = [stmt_node]

        return tails

    def process_pending_labels(self, node) -> None:
        if node.type == "lambda_expression":
            return

        if node.type == "labeled_statement":
            label = self.text(node.child_by_field_name("label"))
            if (
                label in self.jumped_labels
                and label not in self.processed_labels
            ):
                self.process_statements([node], [])

        for child in node.named_children:
            self.process_pending_labels(child)

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