import ast

from frontend.base_parser import BaseParser, CFG, CFGNode


class PythonCFGBuilder:
    def __init__(self, source: str):
        self.source = source
        self.cfg = CFG()
        self.next_id = 1
        self.exit_node = None
        self.loop_stack = []

    def add_node(self, label: str) -> CFGNode:
        node = CFGNode(self.next_id, label)
        self.cfg.add_node(node)
        self.next_id += 1
        return node

    def add_edge(self, source: CFGNode, target: CFGNode, label: str = ""):
        self.cfg.add_edge(source, target, label)

    def text(self, node: ast.AST) -> str:
        source = ast.get_source_segment(self.source, node)
        return source.strip() if source else ast.unparse(node)

    def build(self, statements: list[ast.stmt]) -> CFG:
        entry = self.add_node("Entry")
        self.exit_node = self.add_node("Exit")
        self.cfg.start_node = entry
        self.cfg.end_node = self.exit_node

        tails = self.process_statements(statements, [entry])
        for tail in tails:
            self.add_edge(tail, self.exit_node)
        return self.cfg

    def process_statements(
        self,
        statements: list[ast.stmt],
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        exit_node = self.exit_node
        if exit_node is None:
            raise RuntimeError("CFG exit node has not been initialized")

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
            elif isinstance(statement, ast.Return):
                return_node = self.add_node(self.text(statement))
                for tail in tails:
                    self.add_edge(tail, return_node)
                self.add_edge(return_node, exit_node)
                tails = []
            elif isinstance(statement, ast.Raise):
                raise_node = self.add_node(self.text(statement))
                for tail in tails:
                    self.add_edge(tail, raise_node)
                self.add_edge(raise_node, exit_node)
                tails = []
            elif isinstance(statement, ast.Break):
                tails = self.process_loop_transfer(statement, tails, "break_target")
            elif isinstance(statement, ast.Continue):
                tails = self.process_loop_transfer(statement, tails, "continue_target")
            else:
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
        node = self.add_node(self.text(statement))
        for tail in incoming:
            self.add_edge(tail, node)
        if self.loop_stack:
            self.add_edge(node, self.loop_stack[-1][target_key])
        return []

    def build_condition(
        self,
        expression: ast.expr,
        incoming: list[CFGNode],
        true_target: CFGNode,
        false_target: CFGNode,
    ):
        if isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.Not):
            self.build_condition(expression.operand, incoming, false_target, true_target)
            return

        if isinstance(expression, ast.BoolOp) and len(expression.values) > 1:
            is_and = isinstance(expression.op, ast.And)
            pending = incoming
            for operand in expression.values[:-1]:
                next_operand = self.add_node("AND next" if is_and else "OR next")
                if is_and:
                    self.build_condition(operand, pending, next_operand, false_target)
                else:
                    self.build_condition(operand, pending, true_target, next_operand)
                pending = [next_operand]
            self.build_condition(
                expression.values[-1],
                pending,
                true_target,
                false_target,
            )
            return

        decision = self.add_node(self.text(expression))
        for tail in incoming:
            self.add_edge(tail, decision)
        self.add_edge(decision, true_target, "True")
        self.add_edge(decision, false_target, "False")

    def process_if(self, statement: ast.If, incoming: list[CFGNode]) -> list[CFGNode]:
        true_gate = self.add_node("True branch")
        false_gate = self.add_node("False branch")
        self.build_condition(statement.test, incoming, true_gate, false_gate)

        true_tails = self.process_statements(statement.body, [true_gate])
        false_tails = (
            self.process_statements(statement.orelse, [false_gate])
            if statement.orelse
            else [false_gate]
        )
        return true_tails + false_tails

    def process_while(self, statement: ast.While, incoming: list[CFGNode]) -> list[CFGNode]:
        condition_entry = self.add_node("While condition")
        after_loop = self.add_node("After while")
        for tail in incoming:
            self.add_edge(tail, condition_entry)

        body_entry = self.add_node("While body")
        self.build_condition(statement.test, [condition_entry], body_entry, after_loop)
        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })
        body_tails = self.process_statements(statement.body, [body_entry])
        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry, "Back")
        return [after_loop]

    def process_for(
        self,
        statement: ast.For | ast.AsyncFor,
        incoming: list[CFGNode],
    ) -> list[CFGNode]:
        condition_entry = self.add_node(
            f"For {self.text(statement.target)} in {self.text(statement.iter)}"
        )
        after_loop = self.add_node("After for")
        body_entry = self.add_node("For body")
        for tail in incoming:
            self.add_edge(tail, condition_entry)
        self.add_edge(condition_entry, body_entry, "True")
        self.add_edge(condition_entry, after_loop, "False")

        self.loop_stack.append({
            "break_target": after_loop,
            "continue_target": condition_entry,
        })
        body_tails = self.process_statements(statement.body, [body_entry])
        self.loop_stack.pop()

        for tail in body_tails:
            self.add_edge(tail, condition_entry, "Back")
        return [after_loop]


class PythonParser(BaseParser):
    def parse(self, file_path: str) -> ast.Module:
        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        try:
            tree = ast.parse(source, filename=file_path)
            compile(tree, file_path, "exec")
        except SyntaxError as error:
            raise ValueError(f"Python source contains syntax errors: {error}") from error
        return tree

    def build_cfg(self, file_path: str) -> CFG:
        tree = self.parse(file_path)
        function = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            None,
        )
        if function is not None:
            statements = function.body
        else:
            statements = tree.body
        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        return PythonCFGBuilder(source).build(statements)
