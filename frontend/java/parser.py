from __future__ import annotations

from typing import Optional

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from frontend.base_parser import BaseParser, CFG, CFGNode

JAVA_LANGUAGE = Language(tsjava.language())


class JavaCFGBuilder:
    def __init__(self, source: str):
        self.source = source
        self.data = source.encode("utf-8")
        self.cfg = CFG()
        self.next_id = 1
        self.exit_node: Optional[CFGNode] = None
        self.loop_stack: list[dict[str, CFGNode]] = []
        self.break_stack: list[CFGNode] = []
        self.switch_value_stack: list[CFGNode] = []
        self.finally_stack = []

    def add_node(self, label: str) -> CFGNode:
        label = " ".join((label or "Statement").strip().split())
        if len(label) > 180:
            label = label[:177] + "..."
        node = CFGNode(self.next_id, label)
        self.cfg.add_node(node)
        self.next_id += 1
        return node

    def add_edge(self, source: Optional[CFGNode], target: Optional[CFGNode], label: str = ""):
        if source is not None and target is not None:
            self.cfg.add_edge(source, target, label)

    @staticmethod
    def children(node):
        return list(getattr(node, "named_children", [])) if node is not None else []

    @staticmethod
    def field(node, name):
        if node is None:
            return None
        try:
            return node.child_by_field_name(name)
        except (AttributeError, TypeError):
            return None

    def text(self, node) -> str:
        if node is None:
            return ""
        try:
            return self.data[node.start_byte:node.end_byte].decode("utf-8").strip()
        except (AttributeError, UnicodeDecodeError):
            return getattr(node, "type", "Statement")

    def build(self, body) -> CFG:
        entry = self.add_node("Entry")
        self.exit_node = self.add_node("Exit")
        self.cfg.start_node = entry
        self.cfg.end_node = self.exit_node
        statements = self.children(body) if body.type in {"block", "constructor_body"} else [body]
        tails = self.process_statements(statements, [entry])
        for tail in tails:
            self.add_edge(tail, self.exit_node)
        return self.cfg

    def process_statements(self, statements, incoming):
        tails = incoming
        for statement in statements:
            if not tails:
                break
            if statement.type in {"line_comment", "block_comment"}:
                continue
            tails = self.process_statement(statement, tails)
        return tails

    def process_statement(self, node, incoming):
        kind = node.type
        if kind == "block":
            return self.process_statements(self.children(node), incoming)
        if kind == "if_statement":
            return self.process_if(node, incoming)
        if kind in {"while_statement", "for_statement", "enhanced_for_statement", "do_statement"}:
            return self.process_loop(node, incoming)
        if kind in {"switch_statement", "switch_expression"}:
            return self.process_switch(node, incoming)
        if kind == "try_statement":
            return self.process_try(node, incoming)
        if kind == "assert_statement":
            return self.process_assert(node, incoming)
        if kind in {"synchronized_statement"}:
            body = next((c for c in self.children(node) if c.type == "block"), None)
            gate = self.add_node(self.text(node).split("{")[0].strip() or "synchronized")
            for tail in incoming:
                self.add_edge(tail, gate)
            return self.process_statement(body, [gate]) if body else [gate]
        if kind == "labeled_statement":
            kids = self.children(node)
            return self.process_statement(kids[-1], incoming) if kids else incoming
        if kind in {"return_statement", "throw_statement", "yield_statement"}:
            if kind == "return_statement":
                expression = next(
                    (child for child in self.children(node)
                     if child.type not in {";", "return"}),
                    None,
                )
                if expression is not None and self.contains_control_expression(expression):
                    tails = self.process_control_expressions(expression, incoming)
                    item = self.add_node(self.text(node))
                    for tail in tails:
                        self.add_edge(tail, item)
                    self.route_abrupt(item, self.exit_node)
                    return []
            item = self.add_node(self.text(node))
            for tail in incoming:
                self.add_edge(tail, item)
            if kind == "yield_statement" and self.switch_value_stack:
                target = self.switch_value_stack[-1]
            else:
                target = self.exit_node
            self.route_abrupt(item, target)
            return []
        if kind == "break_statement":
            item = self.add_node(self.text(node))
            for tail in incoming:
                self.add_edge(tail, item)
            target = self.break_stack[-1] if self.break_stack else self.exit_node
            self.route_abrupt(item, target, "Break")
            return []
        if kind == "continue_statement":
            item = self.add_node(self.text(node))
            for tail in incoming:
                self.add_edge(tail, item)
            target = self.loop_stack[-1]["continue"] if self.loop_stack else self.exit_node
            self.route_abrupt(item, target, "Continue")
            return []

        # Declarations, assignments, calls, assertions, empty statements,
        # local classes, and unfamiliar constructs remain visible as CFG nodes.
        tails = self.process_control_expressions(node, incoming)
        item = self.add_node(self.text(node) or kind)
        for tail in tails:
            self.add_edge(tail, item)
        return [item]

    def process_if(self, node, incoming):
        cond = self.field(node, "condition")
        consequence = self.field(node, "consequence")
        alternative = self.field(node, "alternative")
        kids = self.children(node)
        if cond is None:
            cond = next((c for c in kids if c.type not in {"block", "else"}), None)
        if consequence is None:
            candidates = [c for c in kids if c is not cond and c.type != "else"]
            consequence = candidates[0] if candidates else None
        if alternative is None:
            else_node = next((c for c in kids if c.type == "else"), None)
            if else_node is not None:
                alt_kids = self.children(else_node)
                alternative = alt_kids[-1] if alt_kids else None

        yes = self.add_node("True branch")
        no = self.add_node("False branch")
        self.build_condition(cond, incoming, yes, no, f"if ({self.text(cond) or 'condition'})")
        yes_tails = self.process_statement(consequence, [yes]) if consequence else [yes]
        no_tails = self.process_statement(alternative, [no]) if alternative else [no]
        continuing_tails = yes_tails + no_tails
        if not continuing_tails:
            # Both branches terminate (for example, both return or throw).
            return []
        merge = self.add_node("After if")
        for tail in continuing_tails:
            self.add_edge(tail, merge)
        return [merge]

    def build_condition(self, node, incoming, true_target, false_target, label=None):
        while node is not None and node.type in {"parenthesized_expression", "condition"}:
            children = self.children(node)
            if len(children) != 1:
                break
            node = children[0]

        if node is not None and node.type == "unary_expression":
            children = node.children
            if children and children[0].type == "!":
                operand = next((child for child in self.children(node)), None)
                if operand is not None:
                    self.build_condition(operand, incoming, false_target, true_target)
                    return

        if node is not None and node.type == "binary_expression":
            operator = self.field(node, "operator")
            operator_text = self.text(operator)
            left = self.field(node, "left")
            right = self.field(node, "right")
            if operator_text in {"&&", "||"} and left is not None and right is not None:
                next_operand = self.add_node("AND next" if operator_text == "&&" else "OR next")
                if operator_text == "&&":
                    self.build_condition(left, incoming, next_operand, false_target)
                    self.build_condition(right, [next_operand], true_target, false_target)
                else:
                    self.build_condition(left, incoming, true_target, next_operand)
                    self.build_condition(right, [next_operand], true_target, false_target)
                return

        decision = self.add_node(label or self.text(node) or "condition")
        for tail in incoming:
            self.add_edge(tail, decision)
        self.add_edge(decision, true_target, "True")
        self.add_edge(decision, false_target, "False")

    def route_abrupt(self, source, target, label=""):
        if not self.finally_stack:
            self.add_edge(source, target, label)
            return

        finalizer = self.finally_stack.pop()
        tails = self.process_statement(finalizer, [source])
        for tail in tails:
            self.route_abrupt(tail, target, label)
        self.finally_stack.append(finalizer)

    def process_expression(self, node, incoming):
        if node is not None and node.type == "ternary_expression":
            return self.process_ternary(node, incoming)
        item = self.add_node(self.text(node) or "Expression")
        for tail in incoming:
            self.add_edge(tail, item)
        return [item]

    def process_ternary(self, node, incoming):
        condition = self.field(node, "condition")
        consequence = self.field(node, "consequence")
        alternative = self.field(node, "alternative")
        yes = self.add_node("True expression")
        no = self.add_node("False expression")
        self.build_condition(condition, incoming, yes, no)
        yes_tails = self.process_expression(consequence, [yes]) if consequence else [yes]
        no_tails = self.process_expression(alternative, [no]) if alternative else [no]
        merge = self.add_node("After conditional expression")
        for tail in yes_tails + no_tails:
            self.add_edge(tail, merge)
        return [merge]

    def contains_control_expression(self, node):
        if node.type in {"ternary_expression", "switch_expression"}:
            return True
        return any(
            self.contains_control_expression(child)
            for child in self.children(node)
        )

    def process_control_expressions(self, node, incoming):
        if node.type == "ternary_expression":
            return self.process_ternary(node, incoming)
        if node.type == "switch_expression":
            return self.process_switch(node, incoming)

        tails = incoming
        for child in self.children(node):
            if self.contains_control_expression(child):
                tails = self.process_control_expressions(child, tails)
        return tails

    def process_assert(self, node, incoming):
        children = self.children(node)
        condition = next(
            (child for child in children if child.type not in {";", "assert"}),
            None,
        )
        passed = self.add_node(self.text(node))
        failed = self.add_node("AssertionError")
        self.build_condition(condition, incoming, passed, failed)
        self.add_edge(failed, self.exit_node, "False")
        return [passed]

    def process_loop(self, node, incoming):
        kind = node.type
        kids = self.children(node)
        body = self.field(node, "body")
        cond = self.field(node, "condition")
        if body is None:
            body = next((c for c in reversed(kids) if c.type == "block"), None)
        if kind == "do_statement":
            # Java do-while executes the body before testing the condition.
            condition = self.add_node("Do-while condition")
            body_gate = self.add_node("Do-while body")
            after = self.add_node("After do-while")
            for tail in incoming:
                self.add_edge(tail, body_gate)
            self.loop_stack.append({"continue": condition})
            self.break_stack.append(after)
            tails = self.process_statement(body, [body_gate]) if body else [body_gate]
            self.break_stack.pop(); self.loop_stack.pop()
            for tail in tails:
                self.add_edge(tail, condition)
            self.build_condition(cond, [condition], body_gate, after, f"while ({self.text(cond) or 'condition'})")
            return [after]

        if kind == "for_statement":
            # Include initializers/updates in the header label so they are not lost.
            label = f"for ({self.text(node)})"
            body_label = "For body"
            after_label = "After for"
        elif kind == "enhanced_for_statement":
            label = f"for-each ({self.text(node)})"
            body_label = "For body"
            after_label = "After for"
        else:
            label = f"while ({self.text(cond) or 'condition'})"
            body_label = "While body"
            after_label = "After while"

        decision = self.add_node(label)
        body_gate = self.add_node(body_label)
        after = self.add_node(after_label)
        for tail in incoming:
            self.add_edge(tail, decision)
        if kind == "enhanced_for_statement":
            self.add_edge(decision, body_gate, "True")
            self.add_edge(decision, after, "False")
        elif cond is None:
            self.add_edge(decision, body_gate, "True")
        else:
            self.build_condition(cond, [decision], body_gate, after)
        self.loop_stack.append({"continue": decision})
        self.break_stack.append(after)
        tails = self.process_statement(body, [body_gate]) if body else [body_gate]
        self.break_stack.pop(); self.loop_stack.pop()
        for tail in tails:
            self.add_edge(tail, decision, "Back")
        return [after]

    def process_switch(self, node, incoming):
        cond = self.field(node, "condition")
        decision = self.add_node(f"switch ({self.text(cond) or 'value'})")
        after = self.add_node("After switch")
        for tail in incoming:
            self.add_edge(tail, decision)
        body = self.field(node, "body") or next((c for c in self.children(node) if c.type == "switch_block"), None)
        groups = [
            c for c in self.children(body)
            if c.type in {"switch_block_statement_group", "switch_rule"}
        ] if body else []
        if not groups:
            self.add_edge(decision, after, "No matching case")
            return [after]
        self.break_stack.append(after)
        has_default = False
        fallthrough_tails = []
        is_switch_expression = node.type == "switch_expression"
        if is_switch_expression:
            self.switch_value_stack.append(after)
        for group in groups:
            gkids = self.children(group)
            labels = [c for c in gkids if c.type == "switch_label"]
            statements = [c for c in gkids if c not in labels and c.type not in {"->", ":"}]
            gates = []
            for case_label in labels:
                label = self.text(case_label) or "case"
                has_default = has_default or "default" in label.lower()
                gate = self.add_node(label)
                self.add_edge(decision, gate, label)
                gates.append(gate)

            # Arrow rules do not fall through; colon groups do.
            is_rule = group.type == "switch_rule"
            if fallthrough_tails and not is_rule:
                for tail in fallthrough_tails:
                    for gate in gates:
                        self.add_edge(tail, gate, "Fall-through")
            tails = self.process_statements(statements, gates)
            if is_rule:
                for tail in tails:
                    self.add_edge(tail, after)
                fallthrough_tails = []
            else:
                fallthrough_tails = tails
        self.break_stack.pop()
        if is_switch_expression:
            self.switch_value_stack.pop()
        for tail in fallthrough_tails:
            self.add_edge(tail, after)
        if not has_default:
            self.add_edge(decision, after, "No matching case")
        return [after]

    def process_try(self, node, incoming):
        kids = self.children(node)
        body = next((c for c in kids if c.type == "block"), None)
        catches = [c for c in kids if c.type == "catch_clause"]
        finally_clause = next((c for c in kids if c.type == "finally_clause"), None)
        entry = self.add_node("try")
        after = self.add_node("After try")
        for tail in incoming:
            self.add_edge(tail, entry)
        final_body = (
            next((c for c in self.children(finally_clause) if c.type == "block"), None)
            if finally_clause is not None
            else None
        )
        if final_body is not None:
            self.finally_stack.append(final_body)
        branches = self.process_statement(body, [entry]) if body else [entry]
        for catch in catches:
            catch_gate = self.add_node("catch " + self.text(catch)[:90])
            self.add_edge(entry, catch_gate, "Exception")
            catch_body = next((c for c in self.children(catch) if c.type == "block"), None)
            branches.extend(self.process_statement(catch_body, [catch_gate]) if catch_body else [catch_gate])
        if final_body is not None:
            self.finally_stack.pop()
            branches = self.process_statement(final_body, branches) if branches else []
        for tail in branches:
            self.add_edge(tail, after)
        return [after]


class JavaParser(BaseParser):
    """Tree-sitter Java frontend supporting classes and all discovered members.

    A source file may contain multiple top-level/nested classes, constructors,
    methods, and initializer blocks. Each executable body is analyzed as a
    separate CFG region and the regions are joined through a global Entry and
    Exit. The resulting cyclomatic complexity is the sum of the regions' basis
    complexities. Java is not compiled or executed.
    """

    MEMBER_TYPES = {
        "method_declaration",
        "constructor_declaration",
        "compact_constructor_declaration",
        "static_initializer",
        "instance_initializer",
    }
    TYPE_DECLARATIONS = {
        "class_declaration", "interface_declaration", "enum_declaration",
        "record_declaration", "annotation_type_declaration",
    }

    def __init__(self):
        self.parser = Parser(JAVA_LANGUAGE)

    def parse(self, file_path: str):
        with open(file_path, "rb") as file:
            return self.parser.parse(file.read())

    @staticmethod
    def _node_text(data: bytes, node) -> str:
        if node is None:
            return ""
        try:
            return data[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
        except AttributeError:
            return ""

    @staticmethod
    def _field(node, name: str):
        try:
            return node.child_by_field_name(name)
        except (AttributeError, TypeError):
            return None

    def _collect_bodies(self, root, data: bytes):
        """Collect method/constructor/initializer bodies in source order.

        Recursion intentionally continues into member bodies so local classes,
        anonymous classes, and nested declarations can also be discovered.
        A set of source byte ranges prevents duplicates.
        """
        found = []
        seen = set()

        def visit(node, owner=()):
            current_owner = owner
            if node.type in self.TYPE_DECLARATIONS:
                name_node = self._field(node, "name")
                if name_node is None:
                    name_node = next((c for c in JavaCFGBuilder.children(node)
                                      if c.type == "identifier"), None)
                name = self._node_text(data, name_node) or node.type
                current_owner = owner + (name,)

            if node.type in self.MEMBER_TYPES:
                body = next((c for c in JavaCFGBuilder.children(node)
                             if c.type in {"block", "constructor_body"}), None)
                if body is not None and body.start_byte not in seen:
                    name_node = self._field(node, "name")
                    member_name = self._node_text(data, name_node) or node.type
                    qualified_name = ".".join((*current_owner, member_name))
                    found.append((body.start_byte, qualified_name, body))
                    seen.add(body.start_byte)

            # Java initializer blocks are direct block children of class_body,
            # enum_body, or record_body and are not method bodies.
            if node.type in {"class_body", "enum_body", "record_body"}:
                for child in JavaCFGBuilder.children(node):
                    if child.type == "block" and child.start_byte not in seen:
                        prefix = "static initializer" if "static" in self._node_text(data, child)[:20] else "instance initializer"
                        found.append((child.start_byte, ".".join((*current_owner, prefix)), child))
                        seen.add(child.start_byte)

            for child in JavaCFGBuilder.children(node):
                visit(child, current_owner)

        visit(root)
        found.sort(key=lambda item: item[0])
        return found

    def build_cfg(self, file_path: str) -> CFG:
        with open(file_path, "rb") as file:
            data = file.read()
        source = data.decode("utf-8", errors="replace")
        tree = self.parser.parse(data)
        if tree.root_node.has_error:
            raise ValueError(
                "Java source contains syntax errors; check the source code."
            )
        bodies = self._collect_bodies(tree.root_node, data)

        if not bodies:
            raise ValueError(
                "No Java method, constructor, or initializer block was found. "
                "Paste a Java class containing executable code."
            )

        return self._combine_cfgs(source, bodies)

    def _combine_cfgs(self, source: str, bodies) -> CFG:
        """Combine member CFGs without losing node labels or edge labels."""
        combined = CFG()
        next_id = 1
        global_entry = CFGNode(next_id, "Entry")
        combined.add_node(global_entry)
        next_id += 1
        global_exit = CFGNode(next_id, "Exit")
        combined.add_node(global_exit)
        next_id += 1
        combined.start_node = global_entry
        combined.end_node = global_exit

        for _offset, name, body in bodies:
            member_cfg = JavaCFGBuilder(source).build(body)
            id_map = {}
            for old_id, old_node in member_cfg.nodes.items():
                new_node = CFGNode(next_id, old_node.label)
                combined.add_node(new_node)
                id_map[old_id] = new_node
                next_id += 1

            for source_id, target_id in member_cfg.get_edges():
                label = getattr(member_cfg, "edge_labels", {}).get((source_id, target_id), "")
                combined.add_edge(id_map[source_id], id_map[target_id], label)

            member_start = member_cfg.start_node
            member_exit = member_cfg.end_node
            if member_start is not None and member_start.node_id in id_map:
                combined.add_edge(global_entry, id_map[member_start.node_id], f"member: {name}")
            if member_exit is not None and member_exit.node_id in id_map:
                combined.add_edge(id_map[member_exit.node_id], global_exit)

        return combined


__all__ = ["JavaParser", "JavaCFGBuilder"]
