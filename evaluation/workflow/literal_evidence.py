"""Bounded data decoding for observed calculator receipts; never execute code.

Source bindings are syntactic data-presence checks. They do not prove dataflow,
alias immutability or that a program used a particular scientific algorithm.
Consumers must independently bind the complete output proof to the real source.
"""

import ast
import math
import re


class LiteralEvidenceError(ValueError):
    pass


def _tree(text, mode, limit):
    if not isinstance(text, str) or not 1 <= len(text) <= limit:
        raise LiteralEvidenceError("Require bounded nonempty text")
    try:
        tree = ast.parse(text, mode=mode)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise LiteralEvidenceError("Invalid bounded Python syntax") from exc
    pending = [(tree, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > 64 or count > 30000:
            raise LiteralEvidenceError("AST exceeds depth or size bound")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return tree


def _literal(node):
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or type(value) in (str, bool):
            return value
        if type(value) is int and value.bit_length() <= 1024:
            return value
        if type(value) is float and math.isfinite(value):
            return value
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _literal(node.operand)
        if type(value) in (int, float):
            return -value if isinstance(node.op, ast.USub) else value
    elif isinstance(node, ast.List):
        return [_literal(v) for v in node.elts]
    elif isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise LiteralEvidenceError("Dictionary unpacking is not literal data")
            key = _literal(key)
            if not isinstance(key, str) or key in result:
                raise LiteralEvidenceError("Require unique string dictionary keys")
            result[key] = _literal(value)
        return result
    raise LiteralEvidenceError("Only finite JSON-compatible literal data is allowed")


def decode_literal(text):
    return _literal(_tree(text, "eval", 200000).body)


def numeric_receipt_tokens(text):
    """Separate numbers from exact labels in a bounded observed receipt.

    This only supports tolerance-aware comparison of inspected calculator text.
    Every nonnumeric character and the order/number of numeric fields survive;
    identifiers such as g1 or K2 are labels. It neither runs the receipt nor
    establishes that a program implements a valid scientific method.
    """
    if not isinstance(text, str) or not 1 <= len(text) <= 200000:
        raise LiteralEvidenceError("Require bounded nonempty receipt text")
    if re.search(r"\b(?:nan|inf(?:inity)?)\b", text, re.IGNORECASE):
        raise LiteralEvidenceError("Nonfinite receipt values are unsupported")
    pattern = re.compile(
        r"(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![\w.])",
        re.ASCII,
    )
    labels, values, end = [], [], 0
    for match in pattern.finditer(text):
        token = match.group()
        if len(token) > 256 or len(values) >= 10000:
            raise LiteralEvidenceError("Numeric receipt exceeds field bounds")
        value = float(token)
        if not math.isfinite(value):
            raise LiteralEvidenceError("Receipt contains a nonfinite number")
        labels.append(text[end:match.start()])
        values.append(value)
        end = match.end()
    if not values:
        raise LiteralEvidenceError("Receipt contains no numeric evidence")
    labels.append(text[end:])
    return {"labels": labels, "numbers": values}


def _source_literal(node, numpy_aliases):
    """Decode source data containers; wrappers never execute or prove an algorithm."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_source_literal(value, numpy_aliases) for value in node.elts]
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise LiteralEvidenceError("Source dictionary unpacking is not literal")
            key = _literal(key)
            if not isinstance(key, str) or key in result:
                raise LiteralEvidenceError("Require unique string source keys")
            result[key] = _source_literal(value, numpy_aliases)
        return result
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in numpy_aliases
        and node.func.attr == "array"
        and len(node.args) == 1
        and len(node.keywords) <= 1
    ):
        if node.keywords:
            keyword = node.keywords[0]
            if (
                keyword.arg != "dtype"
                or not isinstance(keyword.value, ast.Name)
                or keyword.value.id not in ("float", "int")
            ):
                raise LiteralEvidenceError("Unsupported source array keyword")
        return _source_literal(node.args[0], numpy_aliases)
    return _literal(node)


def literal_assignment_values(code):
    """Collect unambiguous simple top-level literal values, without execution.

    Reject locally reassigned or directly mutated bindings, including mutations
    inside nested syntax. Alias analysis is intentionally not claimed here.
    """
    tree = _tree(code, "exec", 40000)
    stores = {}
    dirty = set()
    namespace_writes = set()

    def root(node):
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores[node.id] = stores.get(node.id, 0) + 1
        if isinstance(node, (ast.Subscript, ast.Attribute)) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            dirty.add(root(node))
            namespace_writes.add(root(node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            dirty.add(root(node.func.value))
    # An array wrapper is recognized only through one unshadowed top-level import.
    imports = {}
    numpy_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or (
                    alias.name.split(".")[0]
                    if isinstance(node, ast.Import)
                    else alias.name
                )
                imports[name] = imports.get(name, 0) + 1
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                name = alias.asname or alias.name
                if (
                    alias.name == "numpy"
                    and imports.get(name) == 1
                    and not stores.get(name)
                    and name not in namespace_writes
                ):
                    numpy_aliases.add(name)
    # Shadowing the dtype markers also makes the wrapper ambiguous.
    if any(stores.get(name) or imports.get(name) for name in ("float", "int")):
        numpy_aliases.clear()
    values = []
    for statement in tree.body:
        if (
            not isinstance(statement, ast.Assign)
            or len(statement.targets) != 1
            or not isinstance(statement.targets[0], ast.Name)
        ):
            continue
        name = statement.targets[0].id
        if stores.get(name) != 1 or name in dirty:
            continue
        try:
            value = _source_literal(statement.value, numpy_aliases)
        except LiteralEvidenceError:
            continue
        values.append(value)
        if len(values) > 256:
            raise LiteralEvidenceError("Too many source literal bindings")
    return values
