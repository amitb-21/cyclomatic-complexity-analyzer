
import ast
from typing import Optional, cast

from frontend.base_parser import BaseParser, CFG, CFGNode


class PythonCFGBuilder:
    """Build a standardized CFG from Python statements."""

    def __init__(self, source: str):
        self.source = source
        self.cfg = CFG()
        self.next_id = 1
        self.exit_node: Optional[CFGNode] = None
        self.loop_stack: list[dict[str, CFGNode]] = []
        self.finally_stack: list[list[ast.stmt]] = []
        self.exception_stack: list[CFGNode] = []

        # Temporary nodes used while constructing if/elif/else branches.
        self.branch_gates: list[CFGNode] = []

    def add_node(self, label: str) -> CFGNode:
        node = CFGNode(self.next_id, label)
        self.cfg.add_node(node)
        self.next_id += 1
        return node

    def add_edge(
        self,
        source: Optional[CFGNode],
        target: Optional[CFGNode],
        label: str = "",
    ) -> None:
        if source is not None and target is not None:
            self.cfg.add_edge(source, target, label)

    def text(self, node: ast.AST) -> str:
        """Return the original source text for an AST node."""
        segment = ast.get_source_segment(self.source, node)
        return segment.strip() if segment else ast.unparse(node)

    def build(self, statements: list[ast.stmt]) -> CFG:
        entry = self.add_node("Entry")
        self.exit_node = self.add_node("Exit")

        self.cfg.start_node = entry
        self.cfg.end_node = self.exit_node

        tails = self.process_statements(statements, [entry])

        for tail in tails:
            self.add_edge(tail, self.exit_node)

        # Replace temporary branch gates with direct labeled edges.
        self.remove_branch_gates()

        return self.cfg

    def remove_branch_gates(self) -> None:
        """
        Remove temporary True/False branch nodes.

        Preserve the incoming decision label when reconnecting each
        predecessor directly to the branch's first CFG node.
        """
        for gate in self.branch_gates:
            if gate.node_id not in self.cfg.nodes:
                continue

            # Save outgoing edges before modifying the graph.
            outgoing = [
                (
                    target,
                    self.cfg.edge_labels.get(
                        (gate.node_id, target.node_id), ""
                    ),
                )
                for target in gate.successors
            ]

            # Find every node that points to this gate.
            incoming_sources = [
                source
                for source in self.cfg.nodes.values()
                if source is not gate and gate in source.successors
            ]

            for source in incoming_sources:
                incoming_label = self.cfg.edge_labels.get(
                    (source.node_id, gate.node_id), ""
                )

                # Remove the predecessor -> temporary-gate edge.
                source.successors.remove(gate)
                self.cfg.edge_labels.pop(
                    (source.node_id, gate.node_id), None
                )

                # Connect the predecessor directly to the branch body.
                for target, outgoing_label in outgoing:
                    self.add_edge(
                        source,
                        target,
                        incoming_label or outgoing_label,
                    )

            # Remove any edge labels involving the temporary gate.
            for key in list(self.cfg.edge_labels):
                if gate.node_id in key:
                    self.cfg.edge_labels.pop(key, None)

            # Remove the temporary node from the graph.
            self.cfg.nodes.pop(gate.node_id, None)

        self.branch_gates.clear()

    def process_statements(
        self,
        statements: list[ast.stmt],
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        tails = incoming

        for statement in statements:
            if not tails:
                break

            if isinstance(statement, ast.If):
                tails = self.process_if(statement, tails)

            elif isinstance(statement, ast.While):
                tails = self.process_while(statement, tails)

            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                tails = self.process_for(statement, tails)

            elif isinstance(statement, ast.Match):
                tails = self.process_match(statement, tails)

            elif isinstance(statement, ast.Assert):
                tails = self.process_assert(statement, tails)

            elif isinstance(statement, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                tails = self.process_try(cast(ast.Try, statement), tails)

            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                # The with statement's body follows its incoming flow.
                # Exception and context-manager failure edges are not
                # modeled in this initial implementation.
                tails = self.process_statements(statement.body, tails)

            elif isinstance(statement, ast.Return):
                expression = statement.value
                if expression is not None:
                    tails = self.process_embedded_conditionals(expression, tails)
                node = self.add_node(self.text(statement))

                for tail in tails:
                    self.add_edge(tail, node)

                assert self.exit_node is not None
                self.route_abrupt(node, self.exit_node)
                tails = []

            elif isinstance(statement, ast.Raise):
                expression = statement.exc
                if expression is not None:
                    tails = self.process_embedded_conditionals(expression, tails)
                node = self.add_node(self.text(statement))

                for tail in tails:
                    self.add_edge(tail, node)

                assert self.exit_node is not None
                target = self.exception_stack[-1] if self.exception_stack else self.exit_node
                self.route_abrupt(node, target, "Exception")
                tails = []

            elif isinstance(statement, ast.Break):
                tails = self.process_loop_transfer(
                    statement, tails, "break_target"
                )

            elif isinstance(statement, ast.Continue):
                tails = self.process_loop_transfer(
                    statement, tails, "continue_target"
                )

            else:
                tails = self.process_embedded_conditionals(statement, tails)
                node = self.add_node(self.text(statement))

                for tail in tails:
                    self.add_edge(tail, node)

                tails = [node]

        return tails

    def process_loop_transfer(
        self,
        statement: ast.Break | ast.Continue,
        incoming: list[CFGNode],
        target_key: str,
    ) -> list[CFGNode]:
        if not self.loop_stack:
            raise ValueError(
                f"{type(statement).__name__.lower()} outside a loop"
            )

        node = self.add_node(self.text(statement))

        for tail in incoming:
            self.add_edge(tail, node)

        self.route_abrupt(node, self.loop_stack[-1][target_key])

        # Break and continue transfer control elsewhere.
        return []

    def route_abrupt(self, source: CFGNode, target: CFGNode, label: str = "") -> None:
        if not self.finally_stack:
            self.add_edge(source, target, label)
            return

        final_body = self.finally_stack.pop()
        tails = self.process_statements(final_body, [source])
        for tail in tails:
            self.route_abrupt(tail, target, label)
        self.finally_stack.append(final_body)

    def contains_conditional_expression(self, node: ast.AST) -> bool:
        return any(
            isinstance(child, ast.IfExp)
            for child in ast.walk(node)
        )

    def process_embedded_conditionals(
        self,
        node: ast.AST,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        if isinstance(node, ast.IfExp):
            true_value = self.add_node(f"then {self.text(node.body)}")
            false_value = self.add_node(f"else {self.text(node.orelse)}")
            self.build_condition(
                node.test,
                incoming,
                true_value,
                false_value,
            )
            true_tails = self.process_embedded_conditionals(
                node.body,
                [true_value],
            )
            false_tails = self.process_embedded_conditionals(
                node.orelse,
                [false_value],
            )
            merge = self.add_node("After conditional expression")
            for tail in true_tails + false_tails:
                self.add_edge(tail, merge)
            return [merge]

        tails = incoming
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr) and self.contains_conditional_expression(child):
                tails = self.process_embedded_conditionals(child, tails)
        return tails

    def process_assert(
        self,
        statement: ast.Assert,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        passed = self.add_node(self.text(statement))
        failed = self.add_node("AssertionError")
        self.build_condition(statement.test, incoming, passed, failed)
        self.add_edge(failed, self.exit_node, "False")
        return [passed]

    @staticmethod
    def is_irrefutable_pattern(pattern: ast.pattern) -> bool:
        if isinstance(pattern, ast.MatchAs):
            return pattern.pattern is None or (
                PythonCFGBuilder.is_irrefutable_pattern(pattern.pattern)
            )
        if isinstance(pattern, ast.MatchOr):
            return any(
                PythonCFGBuilder.is_irrefutable_pattern(child)
                for child in pattern.patterns
            )
        return False

    def process_match(
        self,
        statement: ast.Match,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        selector = self.add_node(f"match {self.text(statement.subject)}")
        after = self.add_node("After match")
        for tail in incoming:
            self.add_edge(tail, selector)

        case_gates = [
            self.add_node(f"case {self.text(case.pattern)}")
            for case in statement.cases
        ]
        for case, gate in zip(statement.cases, case_gates):
            self.add_edge(selector, gate, f"Case {self.text(case.pattern)}")

        has_unconditional_case = any(
            case.guard is None and self.is_irrefutable_pattern(case.pattern)
            for case in statement.cases
        )
        if not has_unconditional_case:
            self.add_edge(selector, after, "No matching case")

        for index, (case, gate) in enumerate(zip(statement.cases, case_gates)):
            body_entry = gate
            if case.guard is not None:
                body_entry = self.add_node("Case guard passed")
                next_case = (
                    case_gates[index + 1]
                    if index + 1 < len(case_gates)
                    else after
                )
                self.build_condition(case.guard, [gate], body_entry, next_case)

            tails = self.process_statements(case.body, [body_entry])
            for tail in tails:
                self.add_edge(tail, after)

        return [after]

    def process_try(
        self,
        statement: ast.Try,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        entry = self.add_node("try")
        for tail in incoming:
            self.add_edge(tail, entry)

        handler_gates = [
            self.add_node(
                f"except {self.text(handler.type) if handler.type else 'all'}"
            )
            for handler in statement.handlers
        ]
        exception_dispatch = None
        if handler_gates:
            exception_dispatch = self.add_node("Exception dispatch")
            self.add_edge(entry, exception_dispatch, "Exception")
            for handler, gate in zip(statement.handlers, handler_gates):
                self.add_edge(
                    exception_dispatch,
                    gate,
                    self.text(handler.type) if handler.type else "Exception",
                )

        if statement.finalbody:
            self.finally_stack.append(statement.finalbody)

        if exception_dispatch is not None:
            self.exception_stack.append(exception_dispatch)
        normal_tails = self.process_statements(statement.body, [entry])
        if exception_dispatch is not None:
            self.exception_stack.pop()

        if normal_tails and statement.orelse:
            normal_tails = self.process_statements(
                statement.orelse,
                normal_tails,
            )

        handler_tails = []
        for handler, gate in zip(statement.handlers, handler_gates):
            handler_tails.extend(
                self.process_statements(handler.body, [gate])
            )

        branches = normal_tails + handler_tails
        if statement.finalbody:
            self.finally_stack.pop()
            branches = self.process_statements(
                statement.finalbody,
                branches,
            ) if branches else []
        return branches

    def build_condition(
        self,
        expression: ast.expr,
        incoming: list[CFGNode],
        true_target: CFGNode,
        false_target: CFGNode,
    ) -> None:
        """Build decision edges, preserving Python short-circuit rules."""

        # not x reverses the true and false destinations.
        if isinstance(expression, ast.UnaryOp) and isinstance(
            expression.op, ast.Not
        ):
            self.build_condition(
                expression.operand,
                incoming,
                false_target,
                true_target,
            )
            return

        # Handle short-circuit and/or expressions.
        if isinstance(expression, ast.BoolOp) and len(expression.values) > 1:
            is_and = isinstance(expression.op, ast.And)
            pending = incoming

            for operand in expression.values[:-1]:
                next_operand = self.add_node(
                    "AND next" if is_and else "OR next"
                )

                if is_and:
                    self.build_condition(
                        operand,
                        pending,
                        next_operand,
                        false_target,
                    )
                else:
                    self.build_condition(
                        operand,
                        pending,
                        true_target,
                        next_operand,
                    )

                pending = [next_operand]

            self.build_condition(
                expression.values[-1],
                pending,
                true_target,
                false_target,
            )
            return

        # Atomic decision: labels belong on outgoing edges.
        decision = self.add_node(self.text(expression))

        for tail in incoming:
            self.add_edge(tail, decision)

        self.add_edge(decision, true_target, "True")
        self.add_edge(decision, false_target, "False")

    def process_if(
        self,
        statement: ast.If,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        # Temporary gates let us build the branch bodies first.
        # They are removed at the end of build().
        true_gate = self.add_node("True branch")
        false_gate = self.add_node("False branch")

        self.branch_gates.extend([true_gate, false_gate])

        self.build_condition(
            statement.test,
            incoming,
            true_gate,
            false_gate,
        )

        true_tails = self.process_statements(
            statement.body,
            [true_gate],
        )

        if statement.orelse:
            false_tails = self.process_statements(
                statement.orelse,
                [false_gate],
            )
        else:
            false_tails = [false_gate]

        return true_tails + false_tails

    def process_while(
        self,
        statement: ast.While,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        condition_entry = self.add_node("While condition")
        after_loop = self.add_node("After while")

        for tail in incoming:
            self.add_edge(tail, condition_entry)

        body_entry = self.add_node("While body")

        # Normal exhaustion executes loop-else, if present.
        if statement.orelse:
            else_entry = self.add_node("While else")
            false_target = else_entry
        else:
            else_entry = None
            false_target = after_loop

        self.build_condition(
            statement.test,
            [condition_entry],
            body_entry,
            false_target,
        )

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })

        body_tails = self.process_statements(
            statement.body,
            [body_entry],
        )

        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry, "Back")

        if else_entry is not None:
            else_tails = self.process_statements(
                statement.orelse,
                [else_entry],
            )

            for tail in else_tails:
                self.add_edge(tail, after_loop)

        return [after_loop]

    def process_for(
        self,
        statement: ast.For | ast.AsyncFor,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        condition_entry = self.add_node(
            f"For {self.text(statement.target)} in "
            f"{self.text(statement.iter)}"
        )
        body_entry = self.add_node("For body")
        after_loop = self.add_node("After for")

        for tail in incoming:
            self.add_edge(tail, condition_entry)

        if statement.orelse:
            else_entry = self.add_node("For else")
            false_target = else_entry
        else:
            else_entry = None
            false_target = after_loop

        # A for-loop decision has two outgoing edges.
        self.add_edge(condition_entry, body_entry, "True")
        self.add_edge(condition_entry, false_target, "False")

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })

        body_tails = self.process_statements(
            statement.body,
            [body_entry],
        )

        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry, "Back")

        if else_entry is not None:
            else_tails = self.process_statements(
                statement.orelse,
                [else_entry],
            )

            for tail in else_tails:
                self.add_edge(tail, after_loop)

        return [after_loop]


class PythonParser(BaseParser):
    """Parse Python source and construct its control-flow graph."""

    def parse(self, file_path: str) -> ast.Module:
        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()

        try:
            tree = ast.parse(source, filename=file_path)
            compile(tree, file_path, "exec")
        except SyntaxError as error:
            raise ValueError(
                f"Python source contains syntax errors: {error}"
            ) from error

        return tree

    def build_cfg(self, file_path: str) -> CFG:
        tree = self.parse(file_path)

        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()

        function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
        functions = [
            node for node in ast.walk(tree)
            if isinstance(node, function_types)
        ]
        functions.sort(key=lambda node: (node.lineno, node.col_offset))
        regions = [
            (node.name, node.body)
            for node in functions
        ]

        module_statements = [
            node for node in tree.body
            if not isinstance(node, (*function_types, ast.ClassDef))
        ]
        if module_statements:
            regions.insert(0, ("module", module_statements))

        classes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        for class_node in classes:
            class_statements = [
                node for node in class_node.body
                if not isinstance(node, (*function_types, ast.ClassDef))
            ]
            if class_statements:
                regions.append((class_node.name, class_statements))

        if not regions:
            regions.append(("module", []))

        member_cfgs = [
            (name, PythonCFGBuilder(source).build(statements))
            for name, statements in regions
        ]
        return self.combine_cfgs(member_cfgs)

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
                combined.add_edge(entry, id_map[member_cfg.start_node.node_id], f"region: {name}")
            if member_cfg.end_node is not None:
                combined.add_edge(id_map[member_cfg.end_node.node_id], exit_node)

        return combined
