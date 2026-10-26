"""Bounded evidence expressions and predicates; never execute submitted code."""

import json
import math
import re
from .values import (
    MissingEvidence,
    pointer,
    _number,
    _equal,
    _unordered,
    _contains_nonfinite,
    _valid_curve,
    _curve_equivalent,
    _json_size,
)


def operand(spec, context):
    """Resolve a literal, a scoped selector or a bounded evidence expression."""
    if "value" in spec:
        return spec["value"]
    if "source" in spec:
        source = spec["source"]
        if source in {"node", "node_arguments"}:
            node = context.get("nodes", {}).get(spec["node"])
            if node is None:
                raise MissingEvidence("Unmatched node " + spec["node"])
            if source == "node_arguments":
                field = (
                    "_effective_arguments"
                    if "_effective_arguments" in node
                    else "arguments"
                )
                if field not in node:
                    raise MissingEvidence("Matched node has no actual arguments")
                value = node[field]
            else:
                value = node.get("output")
        else:
            if source not in context:
                raise MissingEvidence(source)
            value = context[source]
        return pointer(value, spec.get("path", ""))
    operation = spec.get("operation")
    if (
        operation in {"array", "scalar_array"}
        and not 1 <= len(spec.get("args", [])) <= 10000
    ):
        raise MissingEvidence("Evidence arrays require 1 to 10000 scalar operands")
    if operation == "linear_algebra_witness":
        expressions = spec.get("args", [])
        if len(expressions) != 3:
            raise MissingEvidence("Linear algebra witness needs tool, actual arguments and output")
        from .witnesses import witness_certificate
        return witness_certificate(*(operand(v, context) for v in expressions))
    if operation == "select_if_text_equal":
        expressions = spec.get("args", [])
        if not isinstance(expressions, list) or len(expressions) != 4:
            raise MissingEvidence(
                "Text selection requires two comparisons and two explicit branches"
            )
        left, right = (operand(expr, context) for expr in expressions[:2])
        if any(
            not isinstance(value, str) or not 1 <= len(value) <= 2000000
            for value in (left, right)
        ):
            raise MissingEvidence(
                "Text comparison requires two observed bounded nonempty strings"
            )
        # Only an exact input identity permits reuse of the original result.
        # A missing comparison or selected observation always fails; an unused
        # branch is not evidence and must not be evaluated eagerly.
        return operand(expressions[2 if left == right else 3], context)
    args = [operand(arg, context) for arg in spec.get("args", [])]
    if operation == "public_asset_paths":
        if len(args) != 3:
            raise MissingEvidence("Public asset paths require filename, SHA256 and reviewed aliases")
        from .assets import public_asset_paths
        return public_asset_paths(*args)
    if operation == "reviewed_program_identity":
        if len(args) != 1:
            raise MissingEvidence("Reviewed program identity requires one operand")
        from .program_identity import reviewed_program_identity
        return reviewed_program_identity(args[0])
    if operation == "literal_constant":
        from .constants import resolve

        try:
            return resolve(spec, context.get("constants", {}))
        except ValueError as exc:
            raise MissingEvidence(str(exc)) from exc
    if operation == "record_values_by_path":
        if len(args) != 4:
            raise MissingEvidence(
                "Record path selection requires records, two pointers and an identity"
            )
        records, identity_path, identity, value_path = args
        if (
            not isinstance(records, list)
            or not 1 <= len(records) <= 1000
            or any(not isinstance(row, dict) for row in records)
            or any(
                not isinstance(path, str)
                or len(path) > 1000
                or (path and not path.startswith("/"))
                or re.search(r"~(?:[^01]|$)", path)
                for path in (identity_path, value_path)
            )
        ):
            raise MissingEvidence(
                "Record path selection requires bounded objects and strict JSON pointers"
            )

        def scalar(value):
            return value is None or type(value) in (str, bool) or _number(value)

        if not scalar(identity):
            raise MissingEvidence("Record identity must be a finite JSON scalar")
        try:
            encoded_size = _json_size(records, context)
        except (TypeError, ValueError, RecursionError) as exc:
            raise MissingEvidence("Record path selection requires finite JSON") from exc
        if encoded_size > 2000000:
            raise MissingEvidence("Record path selection exceeds the evidence bound")
        selected = []
        for row in records:
            # Resolve both ports in every row: absent evidence is never silently
            # skipped, including a missing value port in a nonmatching row.
            observed_identity = pointer(row, identity_path)
            value = pointer(row, value_path)
            if not scalar(observed_identity):
                raise MissingEvidence(
                    "Observed record identities must be finite scalars"
                )
            if _equal(observed_identity, identity, 0, 0):
                selected.append(value)
        if not selected:
            raise MissingEvidence("No actual record matches the declared identity")
        return selected
    if operation == "molecular_formula_counts":
        # A deliberately narrow decoder for printed molecular atom counts.
        # Charges, condensed formulae, hydrates and fractional cell compositions
        # need their own explicit semantics; never guess their atom inventory.
        if (
            len(args) != 1
            or not isinstance(args[0], str)
            or not 1 <= len(args[0]) <= 1000
        ):
            raise MissingEvidence("Molecular formula requires one bounded string")
        formula = args[0].strip()
        if (
            not formula
            or re.fullmatch(r"(?:[A-Z][a-z]?(?:[1-9][0-9]*)?\s*)+", formula) is None
        ):
            raise MissingEvidence("Require an uncharged flat integer molecular formula")
        symbols = set(
            "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split()
        )
        counts = {}
        for element, printed in re.findall(r"([A-Z][a-z]?)([0-9]*)", formula):
            amount = int(printed or "1")
            if element not in symbols or element in counts or amount > 10**9:
                raise MissingEvidence(
                    "Unknown/repeated element or excessive molecular atom count"
                )
            counts[element] = amount
        if sum(counts.values()) > 10**9:
            raise MissingEvidence("Molecular formula exceeds the atom-count bound")
        return counts
    if operation == "ordered_integer_intersection":
        if len(args) != 2:
            raise MissingEvidence(
                "Boundary intersection requires two ordered integer arrays"
            )
        for values in args:
            if (
                not isinstance(values, list)
                or len(values) > 10000
                or any(
                    type(value) is not int or not 0 <= value <= 10**9
                    for value in values
                )
                or any(a >= b for a, b in zip(values, values[1:]))
            ):
                raise MissingEvidence(
                    "Boundary arrays require distinct ascending bounded nonnegative integers"
                )
        right = set(args[1])
        return [value for value in args[0] if value in right]
    if operation == "inchi_identifier":
        if (
            len(args) != 1
            or not isinstance(args[0], str)
            or not 1 <= len(args[0]) <= 2000000
        ):
            raise MissingEvidence(
                "InChI evidence requires one bounded tool-output string"
            )
        text = args[0].strip()
        candidates = []
        if text.startswith("InChI="):
            candidates = [text]
        elif text.startswith("**SMILES to InChI**"):
            if text.count("**Result:**") == 1:
                candidates = [text.split("**Result:**", 1)[1].strip()]
        elif text.startswith("### SMILES to InChI Conversion"):
            candidates = re.findall(r"(?m)^- InChI: `([^`\r\n]+)`[ \t]*$", text)
        if (
            len(candidates) != 1
            or re.fullmatch(r"InChI=1S?/[!-~]+", candidates[0]) is None
            or "`" in candidates[0]
        ):
            raise MissingEvidence(
                "Require exactly one complete InChI result in a supported output contract"
            )
        return candidates[0]
    if operation == "object_member_or_null":
        # Optional published metadata only. Mandatory scientific observations
        # still require strict pointer access and availability/existence guards.
        # A missing exact member is distinct from a missing/nonobject document.
        if (
            len(args) != 2
            or not isinstance(args[0], dict)
            or not isinstance(args[1], str)
            or not 1 <= len(args[1]) <= 128
        ):
            raise MissingEvidence(
                "Optional metadata lookup requires an object and a bounded exact member name"
            )
        stack, visited = [(args[0], 0)], 0
        while stack:
            value, depth = stack.pop()
            visited += 1
            if visited > 30000 or depth > 64:
                raise MissingEvidence(
                    "Optional metadata object exceeds structural evidence bounds"
                )
            if type(value) is dict:
                if any(type(key) is not str for key in value):
                    raise MissingEvidence(
                        "Optional metadata requires JSON string member names"
                    )
                stack.extend((item, depth + 1) for item in value.values())
            elif type(value) is list:
                stack.extend((item, depth + 1) for item in value)
            elif not (value is None or type(value) in (str, bool) or _number(value)):
                raise MissingEvidence("Optional metadata requires finite JSON cells")
        try:
            encoded_size = _json_size(args[0], context)
        except (TypeError, ValueError, RecursionError) as exc:
            raise MissingEvidence(
                "Optional metadata lookup requires finite JSON"
            ) from exc
        if encoded_size > 2000000 or _contains_nonfinite(args[0]):
            raise MissingEvidence(
                "Optional metadata lookup exceeds finite JSON evidence bounds"
            )
        return args[0][args[1]] if args[1] in args[0] else None
    if operation == "value_at_pointer":
        if len(args) != 2 or not isinstance(args[1], str):
            raise MissingEvidence(
                "Value lookup requires a JSON value and strict pointer"
            )
        value, path = args
        if (path and not path.startswith("/")) or re.search(r"~(?:[^01]|$)", path):
            raise MissingEvidence("Value lookup requires a strict JSON pointer")
        try:
            encoded_size = _json_size(value, context)
        except (TypeError, ValueError) as exc:
            raise MissingEvidence("Value lookup requires finite JSON") from exc
        if encoded_size > 2000000:
            raise MissingEvidence("Value lookup exceeds the evidence size bound")
        return pointer(value, path)
    if operation == "named_numeric_port":
        if (
            len(args) != 2
            or not isinstance(args[0], dict)
            or not isinstance(args[1], list)
            or not 1 <= len(args[1]) <= 8
            or any(
                not isinstance(path, str)
                or not 1 <= len(path) <= 128
                or not path.startswith("/")
                or re.search(r"~(?:[^01]|$)", path)
                for path in args[1]
            )
            or len(set(args[1])) != len(args[1])
        ):
            raise MissingEvidence(
                "Numeric ports require an object and1..8 distinct explicit JSON pointers"
            )
        present = []
        for path in args[1]:
            try:
                present.append(pointer(args[0], path))
            except MissingEvidence:
                continue
        if len(present) != 1 or not _number(present[0]):
            raise MissingEvidence(
                "Exactly one declared numeric port must exist and be finite; no missing/null/text fallback"
            )
        return present[0]
    if operation == "complete_record_rows":
        if len(args) != 1 or not isinstance(args[0], dict):
            raise MissingEvidence(
                "Complete record rows require one observed record-tool output"
            )
        result = args[0]
        if "document" in result and (
            "records" in result or "preview_records" in result
        ):
            raise MissingEvidence("Ambiguous mixed parsed/preview record envelopes")
        if "records" in result:
            rows = result["records"]
            complete = result.get("truncated") is False
            counts = [
                result.get("returned_record_count"),
                result.get("matching_record_count"),
            ]
        elif "preview_records" in result:
            rows = result["preview_records"]
            complete = (
                result.get("preview_truncated") is False
                and result.get("limit_applied") is False
            )
            counts = [
                result.get("preview_record_count"),
                result.get("output_record_count"),
                result.get("matching_record_count"),
            ]
        elif "document" in result:
            # ParseJSONDocument's file mode reads the entire JSON document.
            # Only its explicit source-bound {data:[record,...]} format is a
            # record collection. Inline JSON, arbitrary dictionaries, nested
            # previews and inferred field aliases establish no complete file.
            document = result["document"]
            if (
                not isinstance(document, dict)
                or "data" not in document
                or not isinstance(result.get("source_file"), str)
                or not result["source_file"]
                or not isinstance(result.get("source_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"]) is None
            ):
                raise MissingEvidence(
                    "Parsed record files require full document/data and explicit source path/hash"
                )
            rows = document["data"]
            complete = True
            counts = [len(rows)] if isinstance(rows, list) else []
        else:
            raise MissingEvidence("Observed output has no supported record collection")
        if (
            not complete
            or not isinstance(rows, list)
            or len(rows) > 1000
            or any(not isinstance(row, dict) for row in rows)
            or any(type(count) is not int or count != len(rows) for count in counts)
        ):
            raise MissingEvidence(
                "Observed record collection is truncated, limited or count-inconsistent"
            )
        try:
            encoded_size = _json_size(rows, context)
        except (TypeError, ValueError) as exc:
            raise MissingEvidence("Observed records must be finite JSON") from exc
        if encoded_size > 2000000:
            raise MissingEvidence(
                "Observed record collection exceeds the evidence size bound"
            )
        return rows
    if operation == "source_file_labels":
        if len(args) != 3:
            raise MissingEvidence(
                "File labels require requested labels, observed paths and canonical labels"
            )
        requested, paths, labels = args
        if (
            not isinstance(requested, list)
            or not isinstance(paths, list)
            or not isinstance(labels, list)
            or not 1 <= len(paths) == len(labels) <= 1000
            or len(requested) > 1000
            or any(
                not isinstance(v, str) or not v or len(v) > 4096
                for v in requested + paths + labels
            )
            or any("/" in v or "\\" in v or v in {".", ".."} for v in labels)
            or len(set(labels)) != len(labels)
            or len(set(paths)) != len(paths)
        ):
            raise MissingEvidence(
                "File identity requires bounded unambiguous observed paths and source labels"
            )
        aliases = {}
        for path, label in zip(paths, labels):
            for alias in (path, label, "asset://" + label):
                if alias in aliases and aliases[alias] != label:
                    raise MissingEvidence("Ambiguous source file alias")
                aliases[alias] = label
        # Only exact observed paths and declared portable labels are equivalent.
        # Never strip arbitrary directories: /other/data.csv is not evidence for
        # the observed /release/data.csv merely because their basenames agree.
        # The task's prerequisite nodes must independently bind source identity.
        return [aliases.get(value, value) for value in requested]
    if operation == "coalesce_number":
        if (
            len(args) != 2
            or not _number(args[1])
            or (args[0] is not None and not _number(args[0]))
        ):
            raise MissingEvidence(
                "coalesce_number requires an observed finite number or explicit null, and a finite numeric fallback"
            )
        # Missing selectors already raised above; explicit null is different
        # from absent evidence. Zero/false/string/container coercion is forbidden.
        return args[1] if args[0] is None else args[0]
    if operation == "linear_projection_values":
        if len(args) != 5:
            raise MissingEvidence(
                "Linear projection lookup requires matrix, vector, outputs, source coefficients and source vector"
            )
        matrix, vector, values, coefficients, reference_vector = args
        if (
            not isinstance(matrix, list)
            or not matrix
            or not isinstance(vector, list)
            or not 1 <= len(vector) <= 128
            or not isinstance(values, list)
            or len(values) != len(matrix)
            or not isinstance(coefficients, list)
            or len(coefficients) != len(vector)
            or not isinstance(reference_vector, list)
            or len(reference_vector) != len(vector)
            or len(matrix) * len(vector) > 10000
            or any(
                not _number(v)
                for v in vector + values + coefficients + reference_vector
            )
            or any(
                not isinstance(row, list)
                or len(row) != len(vector)
                or any(not _number(v) for v in row)
                for row in matrix
            )
        ):
            raise MissingEvidence(
                "Linear projection evidence requires finite aligned numeric arrays, at most128components and10000matrix cells"
            )
        tolerance = {k: spec.get(k, 0) for k in ("atol", "rtol")}
        if any(not _number(v) or v < 0 for v in tolerance.values()):
            raise MissingEvidence(
                "Projection matching tolerances must be finite nonnegative numbers"
            )
        preserve_order = spec.get("preserve_component_order", False)
        if type(preserve_order) is not bool:
            raise MissingEvidence("Projection component-order policy must be boolean")
        target = [[c, v] for c, v in zip(coefficients, reference_vector)]
        selected = [
            value
            for row, value in zip(matrix, values)
            if (
                _equal(
                    [[c, v] for c, v in zip(row, vector)],
                    target,
                    tolerance["atol"],
                    tolerance["rtol"],
                )
                if preserve_order
                else _unordered(
                    [[c, v] for c, v in zip(row, vector)], target, tolerance
                )
            )
        ]
        if not selected:
            raise MissingEvidence(
                "No actual row contains the complete source-grounded paired linear functional"
            )
        # Return EVERY matching actual result, including duplicates; callers
        # must check all of them rather than selecting a convenient answer.
        return selected
    if operation == "numeric_value_for_row":
        if len(args) != 3:
            raise MissingEvidence(
                "numeric_value_for_row requires feature rows, scalar values and one complete row key"
            )
        rows, values, target = args
        if (
            not isinstance(rows, list)
            or not 1 <= len(rows) <= 10000
            or not isinstance(values, list)
            or len(values) != len(rows)
            or not isinstance(rows[0], list)
            or not 1 <= len(rows[0]) <= 1000
            or len(rows) * (len(rows[0]) + 1) > 20000
        ):
            raise MissingEvidence(
                "Require aligned nonempty feature rows and scalar values within20000cells"
            )
        width = len(rows[0])
        if any(
            not isinstance(row, list)
            or len(row) != width
            or any(not _number(value) for value in row)
            for row in rows
        ):
            raise MissingEvidence(
                "Every feature row must be rectangular finite real numeric evidence"
            )
        if any(not _number(value) for value in values):
            raise MissingEvidence(
                "Every scalar value must be finite real numeric evidence"
            )
        if (
            not isinstance(target, list)
            or len(target) != width
            or any(not _number(value) for value in target)
        ):
            raise MissingEvidence(
                "Target must be one complete finite numeric feature row"
            )
        lookup = {}
        for row, value in zip(rows, values):
            key = tuple(row)
            if key in lookup and lookup[key] != value:
                raise MissingEvidence(
                    "Repeated actual row keys have conflicting scalar values"
                )
            lookup[key] = value
        key = tuple(target)
        if key not in lookup:
            raise MissingEvidence("No observed value for the exact complete row key")
        # Identity lookup only: no fit, averaging, rounding or scientific inference.
        return lookup[key]
    if operation == "numeric_receipt_tokens":
        from .literal_evidence import numeric_receipt_tokens, LiteralEvidenceError

        if len(args) != 1:
            raise MissingEvidence("Numeric receipt requires one observed text")
        try:
            return numeric_receipt_tokens(args[0])
        except LiteralEvidenceError as exc:
            raise MissingEvidence(str(exc)) from exc
    if operation == "python_literal_lines":
        # Decode calculator receipts as data, preserving line order. Never run
        # expressions, import names, or infer a scientific method from stdout.
        if len(args) != 1 or not isinstance(args[0], str) or len(args[0]) > 200000:
            raise MissingEvidence("Require one bounded literal-lines receipt")
        lines = [line for line in args[0].splitlines() if line.strip()]
        if not 1 <= len(lines) <= 1000:
            raise MissingEvidence("Literal receipt requires 1 to 1000 nonempty lines")
        from .literal_evidence import decode_literal, LiteralEvidenceError

        try:
            return [decode_literal(line) for line in lines]
        except LiteralEvidenceError as exc:
            raise MissingEvidence(str(exc)) from exc
    if operation == "python_literal_value":
        if (
            len(args) != 2
            or not isinstance(args[1], str)
            or len(args[1]) > 1000
            or (args[1] and not args[1].startswith("/"))
            or re.search(r"~(?:[^01]|$)", args[1])
        ):
            raise MissingEvidence(
                "Require observed literal text and one strict bounded pointer"
            )
        from evaluation.workflow.literal_evidence import (
            decode_literal,
            LiteralEvidenceError,
        )

        try:
            return pointer(decode_literal(args[0]), args[1])
        except LiteralEvidenceError as exc:
            raise MissingEvidence(str(exc)) from exc
    if operation == "python_literal_assignments":
        if len(args) != 1:
            raise MissingEvidence(
                "Literal source lookup requires one bounded code string"
            )
        from evaluation.workflow.literal_evidence import (
            literal_assignment_values,
            LiteralEvidenceError,
        )

        try:
            return literal_assignment_values(args[0])
        except LiteralEvidenceError as exc:
            raise MissingEvidence(str(exc)) from exc
    if operation == "matrix_value_by_ids":
        if len(args) != 4:
            raise MissingEvidence(
                "Matrix lookup requires one matrix, axis IDs and two IDs"
            )
        matrix, ids, first_id, second_id = args
        if (
            not isinstance(ids, list)
            or not 2 <= len(ids) <= 20
            or any(not isinstance(v, str) or not 1 <= len(v) <= 200 for v in ids)
            or len(set(ids)) != len(ids)
            or not isinstance(first_id, str)
            or first_id not in ids
            or not isinstance(second_id, str)
            or second_id not in ids
            or not isinstance(matrix, list)
            or len(matrix) != len(ids)
            or any(
                not isinstance(row, list)
                or len(row) != len(ids)
                or any(not _number(v) for v in row)
                for row in matrix
            )
        ):
            raise MissingEvidence(
                "Require a complete finite square matrix with2..20 unique bounded string axis IDs and two existing IDs"
            )
        # Exact label lookup only. Symmetry, distance units, correspondence and
        # the scientific algorithm are checked by the surrounding tool rules.
        return matrix[ids.index(first_id)][ids.index(second_id)]
    if operation == "coordinate_set_for_id":
        if len(args) != 3:
            raise MissingEvidence(
                "coordinate_set_for_id requires IDs, coordinate sets and one ID"
            )
        ids, sets, identity = args
        if (
            not isinstance(ids, list)
            or not 2 <= len(ids) <= 20
            or any(
                not isinstance(value, str) or not 1 <= len(value) <= 200
                for value in ids
            )
            or len(set(ids)) != len(ids)
            or not isinstance(identity, str)
            or identity not in ids
            or not isinstance(sets, list)
            or len(sets) != len(ids)
        ):
            raise MissingEvidence(
                "Require 2..20 distinct bounded string IDs paired with complete coordinate sets and an existing ID"
            )
        first = sets[0]
        if not isinstance(first, list) or not 3 <= len(first) <= 256:
            raise MissingEvidence(
                "Coordinate sets require 3..256 corresponding 3D points"
            )
        point_count = len(first)
        if len(ids) * point_count * 3 > 10000:
            raise MissingEvidence("Coordinate evidence exceeds10000 scalar coordinates")
        for points in sets:
            if not isinstance(points, list) or len(points) != point_count:
                raise MissingEvidence("Coordinate evidence requires equal point counts")
            if any(
                not isinstance(point, list)
                or len(point) != 3
                or any(not _number(value) for value in point)
                for point in points
            ):
                raise MissingEvidence(
                    "Coordinate evidence requires finite real 3D points without coercion"
                )
        # Resolve one supplied ID with its complete paired coordinates. This
        # never aligns, reorders points, normalizes units, or computes geometry.
        return [list(point) for point in sets[ids.index(identity)]]
    if operation == "integer_translation_span":
        # A geometric periodic dimension is a rational row-space descriptor,
        # not a choice of spanning tree or generator order. Exact elimination
        # avoids treating an almost-planar vector as a valid lattice shift.
        from fractions import Fraction

        if (
            len(args) != 1
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 1000
            or any(
                not isinstance(row, list)
                or len(row) != 3
                or any(not _number(v) or int(v) != v or abs(v) > 1000000 for v in row)
                for row in args[0]
            )
        ):
            raise MissingEvidence(
                "Require1..1000 integer three-coordinate translations, absolute entries <=1000000"
            )
        rows = [[Fraction(int(v)) for v in row] for row in args[0]]
        pivot = 0
        for column in range(3):
            selected = next(
                (j for j in range(pivot, len(rows)) if rows[j][column]), None
            )
            if selected is None:
                continue
            rows[pivot], rows[selected] = rows[selected], rows[pivot]
            scale = rows[pivot][column]
            rows[pivot] = [v / scale for v in rows[pivot]]
            for j in range(len(rows)):
                if j != pivot:
                    scale = rows[j][column]
                    rows[j] = [v - scale * w for v, w in zip(rows[j], rows[pivot])]
            pivot += 1
        # Canonical rational strings preserve exact equality. This compares
        # spans only; it does not assert equality of primitive lattice periods.
        return [[str(v) for v in row] for row in rows[:pivot]]
    if operation == "average_ranks":
        if (
            len(args) != 1
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 10000
            or any(not _number(value) for value in args[0])
        ):
            raise MissingEvidence(
                "average_ranks requires one finite numeric vector of length1..10000"
            )
        values = args[0]
        order = sorted(range(len(values)), key=values.__getitem__)
        ranks = [None] * len(values)
        start = 0
        while start < len(order):
            end = start + 1
            while end < len(order) and values[order[end]] == values[order[start]]:
                end += 1
            # Equal numeric values share their mean 1-based position. No
            # approximate tie tolerance or category/string coercion is inferred.
            rank = (start + 1 + end) / 2
            for index in order[start:end]:
                ranks[index] = rank
            start = end
        return ranks
    if operation == "normalize_protein_strings":
        if (
            len(args) != 1
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 100
        ):
            raise MissingEvidence("Require one list of 1..100 protein strings")
        sequences = args[0]
        if any(not isinstance(sequence, str) for sequence in sequences):
            raise MissingEvidence("Protein evidence requires strings without coercion")
        if sum(map(len, sequences)) > 2000000:
            raise MissingEvidence("Protein evidence exceeds 2000000 raw characters")
        normalized = []
        canonical = set("ACDEFGHIKLMNPQRSTVWY")
        for sequence in sequences:
            value = "".join(sequence.split()).upper().rstrip("*")
            if not 1 <= len(value) <= 10000 or set(value) - canonical:
                raise MissingEvidence("Require 1..10000 normalized canonical residues")
            normalized.append(value)
        return normalized
    if operation == "interval_union":
        if len(args) != 2:
            raise MissingEvidence(
                "interval_union requires intervals and actual source length"
            )

        def bounded_index(value, maximum):
            if not _number(value) or int(value) != value or not 0 <= value <= maximum:
                raise MissingEvidence(
                    "Interval coordinates must be bounded mathematical integers"
                )
            return int(value)

        source_length = bounded_index(args[1], 2000000)
        pairs = args[0]
        if (
            source_length < 1
            or not isinstance(pairs, list)
            or not 1 <= len(pairs) <= 1000
        ):
            raise MissingEvidence(
                "Interval coverage requires a nonempty bounded source and1..1000pairs"
            )
        merged = []
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise MissingEvidence("Interval coverage needs [start,stop] pairs")
            start, stop = [bounded_index(v, source_length) for v in pair]
            if start >= stop or (merged and start < merged[-1][1]):
                raise MissingEvidence(
                    "Interval coverage must be nonempty, ordered and nonoverlapping"
                )
            if merged and start == merged[-1][1]:
                merged[-1][1] = stop
            else:
                merged.append([start, stop])
        return merged
    if operation == "count_occurrences":
        if (
            len(args) != 2
            or not isinstance(args[0], str)
            or len(args[0]) > 2000000
            or not isinstance(args[1], str)
            or len(args[1]) != 1
        ):
            raise MissingEvidence(
                "Character count requires bounded text and one literal character"
            )
        return args[0].count(args[1])
    if operation == "text_between":
        if (
            len(args) != 3
            or any(not isinstance(value, str) for value in args)
            or len(args[0]) > 2000000
            or any(not 1 <= len(marker) <= 1024 for marker in args[1:])
        ):
            raise MissingEvidence("text_between requires bounded text and two markers")
        text, start, end = args
        if text.count(start) != 1:
            raise MissingEvidence("Text evidence needs exactly one start marker")
        after = text.split(start, 1)[1]
        if end not in after:
            raise MissingEvidence("Text evidence has no closing marker")
        return after.split(end, 1)[0]
    if operation == "closed_numeric_expression":
        if len(args) != 1:
            raise MissingEvidence("closed_numeric_expression requires one text operand")
        from evaluation.workflow.numeric_expression import (
            decode_numeric_expression,
            NumericExpressionError,
        )

        try:
            return decode_numeric_expression(args[0])
        except NumericExpressionError as exc:
            raise MissingEvidence(str(exc)) from exc
    if operation == "numeric_matrix":
        if len(args) != 1 or not isinstance(args[0], str) or len(args[0]) > 2000000:
            raise MissingEvidence("numeric_matrix requires bounded whitespace text")
        lines = args[0].strip().splitlines()
        if not 1 <= len(lines) <= 1000:
            raise MissingEvidence("Numeric text matrix needs 1 to 1000 rows")
        tokens = [line.split() for line in lines]
        width = len(tokens[0])
        if (
            not 1 <= width <= 1000
            or len(tokens) * width > 10000
            or any(len(row) != width for row in tokens)
        ):
            raise MissingEvidence("Numeric text matrix must be bounded and rectangular")
        numeric = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", re.ASCII)
        if any(
            len(token) > 256 or numeric.fullmatch(token) is None
            for row in tokens
            for token in row
        ):
            raise MissingEvidence("Numeric text matrix contains a non-numeric token")
        matrix = [[float(token) for token in row] for row in tokens]
        if any(not math.isfinite(value) for row in matrix for value in row):
            raise MissingEvidence("Numeric text matrix contains nonfinite values")
        return matrix
    if operation == "column_affine":
        if len(args) != 3:
            raise MissingEvidence(
                "column_affine requires a matrix, offsets and positive scales"
            )
        matrix, offsets, scales = args
        if (
            not isinstance(matrix, list)
            or not 1 <= len(matrix) <= 10000
            or not isinstance(offsets, list)
            or not 1 <= len(offsets) <= 1000
            or not isinstance(scales, list)
            or len(scales) != len(offsets)
            or len(matrix) * len(offsets) > 10000
            or any(not _number(v) for v in offsets)
            or any(not _number(v) or v <= 0 for v in scales)
            or any(
                not isinstance(row, list)
                or len(row) != len(offsets)
                or any(not _number(v) for v in row)
                for row in matrix
            )
        ):
            raise MissingEvidence(
                "Column affine evidence requires a bounded finite matrix and aligned explicit offsets and positive scales"
            )
        result = [
            [(v - offset) / scale for v, offset, scale in zip(row, offsets, scales)]
            for row in matrix
        ]
        if any(not _number(v) for row in result for v in row):
            raise MissingEvidence("Nonfinite column affine result")
        return result
    if operation == "array":
        if not all(_number(value) for value in args):
            raise MissingEvidence("Numeric array requires finite numeric scalars")
        return args
    if operation == "scalar_array":
        if any(
            not (value is None or type(value) in (str, bool) or _number(value))
            for value in args
        ):
            raise MissingEvidence("Scalar arrays require finite JSON scalar operands")
        return args
    if operation in {"numeric_rows", "zero_pad_numeric_matrix"}:
        matrix = args if operation == "numeric_rows" else (args[0] if args else None)
        if (
            not isinstance(matrix, list)
            or not 1 <= len(matrix) <= 10000
            or not isinstance(matrix[0], list)
            or not 1 <= len(matrix[0]) <= 1000
            or len(matrix) * len(matrix[0]) > 10000
            or any(
                not isinstance(row, list)
                or len(row) != len(matrix[0])
                or any(not _number(value) for value in row)
                for row in matrix
            )
        ):
            raise MissingEvidence(
                "Numeric rows require a bounded finite rectangular matrix"
            )
        if operation == "numeric_rows":
            return matrix
        if (
            len(args) != 3
            or type(args[1]) is not int
            or type(args[2]) is not int
            or not len(matrix) <= args[1] <= 10000
            or not len(matrix[0]) <= args[2] <= 1000
            or args[1] * args[2] > 10000
        ):
            raise MissingEvidence(
                "Zero extension requires bounded integer dimensions without truncation"
            )
        rows, columns = args[1:]
        return [row + [0] * (columns - len(row)) for row in matrix] + [
            [0] * columns for _ in range(rows - len(matrix))
        ]
    if operation == "records_matching":
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 10000
            or any(not isinstance(row, dict) for row in args[0])
            or not isinstance(args[1], dict)
            or not 1 <= len(args[1]) <= 20
            or any(not isinstance(key, str) or not key for key in args[1])
            or len(args[0]) * len(args[1]) > 20000
        ):
            raise MissingEvidence(
                "records_matching requires bounded records and1..20 literal field conditions"
            )
        records, conditions = args

        def scalar(value):
            return value is None or type(value) in (str, bool) or _number(value)

        if any(not scalar(value) for value in conditions.values()):
            raise MissingEvidence(
                "records_matching conditions require finite JSON scalars"
            )
        # Inspect every condition field even on rows excluded by another key.
        # Missing evidence must not silently become a different scientific cohort.
        if any(key not in row for row in records for key in conditions):
            raise MissingEvidence("records_matching cannot infer missing field values")
        if any(not scalar(row[key]) for row in records for key in conditions):
            raise MissingEvidence(
                "records_matching source condition cells require finite JSON scalars"
            )
        inspected = [
            *conditions.values(),
            *(row[key] for row in records for key in conditions),
        ]
        if sum(len(value) for value in inspected if isinstance(value, str)) > 2000000:
            raise MissingEvidence(
                "records_matching exceeds2000000 inspected characters"
            )

        def same(left, right):
            # No whitespace trimming, case folding, numeric tolerance or bool→1.
            return (_number(left) and _number(right) and left == right) or (
                type(left) is type(right) and left == right
            )

        return [
            row
            for row in records
            if all(same(row[key], value) for key, value in conditions.items())
        ]
    if operation == "matrix_axis_profile":
        if (
            len(args) != 1
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 128
        ):
            raise MissingEvidence(
                "matrix_axis_profile requires a bounded nonempty matrix"
            )
        matrix = args[0]
        width = len(matrix[0]) if isinstance(matrix[0], list) else 0
        if (
            not 1 <= width <= 1000
            or len(matrix) * width > 10000
            or any(
                not isinstance(row, list)
                or len(row) != width
                or any(not _number(v) for v in row)
                for row in matrix
            )
        ):
            raise MissingEvidence(
                "matrix_axis_profile requires a rectangular finite real matrix"
            )
        profiles = [tuple(sorted(row)) for row in matrix]
        if len(set(profiles)) != len(profiles):
            raise MissingEvidence(
                "Ambiguous row profiles require a different explicit identity route"
            )
        aligned = [row for _, row in sorted(zip(profiles, matrix))]
        # Retain full column vectors and their multiplicities. Independent
        # per-row shuffles cannot masquerade as one shared feature permutation.
        return sorted([list(column) for column in zip(*aligned)])
    if operation == "records_nonnull":
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or len(args[0]) > 10000
            or any(not isinstance(row, dict) for row in args[0])
            or not isinstance(args[1], list)
            or not 1 <= len(args[1]) <= 1000
            or any(
                not isinstance(key, str) or not 1 <= len(key) <= 1024 for key in args[1]
            )
            or len(set(args[1])) != len(args[1])
            or len(args[0]) * len(args[1]) > 10000
        ):
            raise MissingEvidence(
                "records_nonnull requires bounded object rows and distinct explicit field names"
            )
        records, columns = args
        if any(key not in row for row in records for key in columns):
            raise MissingEvidence("An absent field is not an explicit null observation")
        return [row for row in records if all(row[key] is not None for key in columns)]
    if operation == "record_field_presence":
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 10000
            or any(not isinstance(row, dict) for row in args[0])
            or not isinstance(args[1], str)
            or not 1 <= len(args[1]) <= 1024
        ):
            raise MissingEvidence(
                "record_field_presence requires bounded object records and a field name"
            )
        return [args[1] in row for row in args[0]]
    if operation == "records_columns":
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 10000
            or any(not isinstance(row, dict) for row in args[0])
            or not isinstance(args[1], list)
            or not 1 <= len(args[1]) <= 1000
            or any(not isinstance(key, str) or not key for key in args[1])
            or len(set(args[1])) != len(args[1])
            or len(args[0]) * len(args[1]) > 10000
        ):
            raise MissingEvidence(
                "records_columns requires bounded records and distinct column names"
            )
        records, columns = args
        if any(key not in row for row in records for key in columns):
            raise MissingEvidence(
                "records_columns cannot replace absent fields with null"
            )
        result = [[row[key] for key in columns] for row in records]
        if any(
            not (value is None or type(value) in (str, bool, int, float))
            or (type(value) is float and not math.isfinite(value))
            for row in result
            for value in row
        ):
            raise MissingEvidence(
                "records_columns requires finite scalar or explicit null values"
            )
        return result
    if operation == "join":
        # Legacy sequence tools accept a delimited string. Check that string
        # against the actual upstream records without embedding expected data.
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 1000
            or any(not isinstance(value, str) for value in args[0])
            or not isinstance(args[1], str)
            or len(args[1]) > 1000
        ):
            raise MissingEvidence("join requires bounded strings and a separator")
        parts, separator = args
        size = sum(len(value) for value in parts) + len(separator) * (len(parts) - 1)
        if size > 2000000:
            raise MissingEvidence("join result exceeds the evidence size limit")
        return separator.join(parts)
    if operation == "column":
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 10000
            or type(args[1]) is not int
            or args[1] < 0
        ):
            raise MissingEvidence(
                "column requires a bounded matrix and nonnegative integer index"
            )
        matrix, index = args
        width = len(matrix[0]) if isinstance(matrix[0], list) else 0
        if (
            not 1 <= width <= 1000
            or index >= width
            or any(not isinstance(row, list) or len(row) != width for row in matrix)
        ):
            raise MissingEvidence(
                "column requires rectangular rows and an in-range index"
            )
        values = [row[index] for row in matrix]
        if any(
            not (value is None or type(value) in (str, bool, int, float))
            or (type(value) is float and not math.isfinite(value))
            for value in values
        ):
            raise MissingEvidence("column values must be finite scalars or null")
        return values
    if operation == "partition_profile":
        # Cluster numbers are names, whereas specimen row identity is not.
        # Quality metrics also give numeric -1 the special meaning of noise.
        if (
            len(args) != 2
            or not isinstance(args[0], list)
            or not 1 <= len(args[0]) <= 10000
            or type(args[1]) is not bool
        ):
            raise MissingEvidence(
                "partition_profile requires bounded labels and a noise-policy boolean"
            )
        labels, preserve_noise = args
        if (
            any(type(v) not in (str, int) for v in labels)
            or sum(len(v) for v in labels if isinstance(v, str)) > 2000000
        ):
            raise MissingEvidence(
                "partition_profile requires string/integer labels within the text limit"
            )
        names = {}
        memberships = []
        for label in labels:
            key = (type(label), label)
            if key not in names:
                names[key] = len(names)
            memberships.append(names[key])
        return {
            "memberships": memberships,
            "noise_mask": (
                [type(v) is int and v == -1 for v in labels] if preserve_noise else None
            ),
        }
    if operation == "paired_rows":
        # Compare complete aligned pairs as a multiset, for either feature-row
        # targets or truth/prediction vectors. Separate multiset comparisons
        # would silently permit broken alignment.
        if (
            len(args) != 2
            or any(not isinstance(value, list) for value in args)
            or not 1 <= len(args[0]) <= 10000
            or len(args[0]) != len(args[1])
        ):
            raise MissingEvidence(
                "paired_rows requires two aligned lists of length 1..10000"
            )
        widths = []
        for values in args:
            matrix = isinstance(values[0], list)
            width = len(values[0]) if matrix else 1
            if not 1 <= width <= 1000 or any(
                isinstance(value, list) != matrix or (matrix and len(value) != width)
                for value in values
            ):
                raise MissingEvidence(
                    "paired_rows requires scalar vectors or rectangular rows on each side"
                )
            widths.append(width)
            scalars = (
                (cell for row in values for cell in row) if matrix else iter(values)
            )
            if any(
                not (value is None or type(value) in (str, bool, int, float))
                or (type(value) in (int, float) and not _number(value))
                for value in scalars
            ):
                raise MissingEvidence("paired_rows requires finite scalar cells")
        if len(args[0]) * sum(widths) > 20000:
            raise MissingEvidence("paired_rows exceeds 20000 paired cells")
        return [[row, target] for row, target in zip(*args)]
    if operation == "json_value":
        if len(args) != 2 or not isinstance(args[0], str) or len(args[0]) > 2000000:
            raise MissingEvidence(
                "json_value requires a bounded JSON string and pointer"
            )
        raw, path = args
        if (
            not isinstance(path, str)
            or (path and not path.startswith("/"))
            or re.search(r"~(?:[^01]|$)", path)
        ):
            raise MissingEvidence("json_value requires a strict JSON pointer")

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("Duplicate JSON key")
                result[key] = value
            return result

        def constant(value):
            raise ValueError("Nonstandard JSON constant: " + value)

        try:
            decoded = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
            if _contains_nonfinite(decoded):
                raise ValueError("Nonfinite decoded evidence")
        except (ValueError, TypeError, RecursionError, OverflowError) as error:
            raise MissingEvidence("Invalid finite JSON evidence") from error
        return pointer(decoded, path)
    if operation == "record_value":
        if len(args) != 4:
            raise ValueError(
                "record_value requires records, identity key, scalar ID and pointer"
            )
        records, key, identity, path = args
        if (
            not isinstance(records, list)
            or not 1 <= len(records) <= 1000
            or any(not isinstance(row, dict) for row in records)
            or not isinstance(key, str)
            or not key
            or (identity is not None and type(identity) not in (str, int, float, bool))
            or _contains_nonfinite(identity)
        ):
            raise MissingEvidence(
                "record_value requires bounded object records and an exact scalar identity"
            )
        if (
            not isinstance(path, str)
            or (path != "" and not path.startswith("/"))
            or re.search(r"~(?:[^01]|$)", path)
        ):
            raise MissingEvidence("record_value target requires a strict JSON pointer")
        matched = [row for row in records if key in row and _equal(row[key], identity)]
        if len(matched) != 1:
            raise MissingEvidence(
                "record_value identity must have exactly one matching record"
            )
        return pointer(matched[0], path)
    if operation == "slice":
        if (
            len(args) != 3
            or not isinstance(args[0], (str, list))
            or any(type(v) is not int for v in args[1:])
            or not 0 <= args[1] <= args[2] <= len(args[0])
        ):
            raise MissingEvidence(
                "slice requires a string/list and bounded nonnegative integer start/stop"
            )
        return args[0][args[1] : args[2]]
    if operation == "common_interval":
        if len(args) != 2 or any(
            not isinstance(v, list)
            or len(v) < 2
            or not all(_number(x) for x in v)
            or not all(a < b for a, b in zip(v, v[1:]))
            for v in args
        ):
            raise MissingEvidence(
                "Common interval requires two strictly increasing finite grids"
            )
        result = [max(v[0] for v in args), min(v[-1] for v in args)]
        if result[0] >= result[1]:
            raise MissingEvidence("Curves have no common interval of positive width")
        return result
    if operation == "curve_spec":
        if len(args) != 4:
            raise ValueError(
                "curve_spec requires source x, source y, baseline and interval"
            )
        x, y, baseline, interval = args
        if (
            not _valid_curve(x, y)
            or not _number(baseline)
            or not isinstance(interval, list)
            or len(interval) != 2
            or not all(_number(v) for v in interval)
            or not x[0] <= interval[0] < interval[1] <= x[-1]
        ):
            raise MissingEvidence(
                "Curve source/baseline/interval is invalid or requires extrapolation"
            )
        return {
            "source_x": x,
            "source_y": y,
            "baseline": baseline,
            "interval": interval,
        }
    if operation in {"argmin", "argmax"}:
        if len(args) != 1 or not isinstance(args[0], list) or not args[0]:
            raise MissingEvidence("Ranking requires nonempty observed rows")
        rows = args[0]
        values = [pointer(row, spec["value_path"]) for row in rows]
        if not all(_number(v) for v in values):
            raise MissingEvidence("Ranking contains nonfinite or nonnumeric values")
        extreme = (min if operation == "argmin" else max)(values)
        return [
            pointer(row, spec["id_path"])
            for row, value in zip(rows, values)
            if abs(value - extreme)
            <= spec.get("tie_atol", 0) + spec.get("tie_rtol", 0) * abs(extreme)
        ]
    if operation == "length" and len(args) == 1:
        return len(args[0])
    if operation in {"sum", "mean", "min", "max"} and len(args) == 1:
        values = args[0]
        if (
            not isinstance(values, list)
            or not values
            or not all(_number(v) for v in values)
        ):
            raise MissingEvidence("Reduction requires nonempty finite numeric values")
        result = {
            "sum": sum,
            "mean": lambda v: sum(v) / len(v),
            "min": min,
            "max": max,
        }[operation](values)
        if not _number(result):
            raise MissingEvidence("Nonfinite reduction result")
        return result
    if not all(_number(v) for v in args):
        raise MissingEvidence("Arithmetic requires finite numbers")
    if operation == "abs" and len(args) == 1:
        result = abs(args[0])
    elif operation == "natural_log" and len(args) == 1:
        if args[0] <= 0:
            raise MissingEvidence("Natural logarithm requires a positive scalar")
        result = math.log(args[0])
    elif operation == "exponential" and len(args) == 1:
        try:
            result = math.exp(args[0])
        except OverflowError as exc:
            raise MissingEvidence(
                "Exponential result overflows finite numbers"
            ) from exc
        if result == 0:
            raise MissingEvidence("Nonzero exponential underflows to zero")
    elif operation in {"add", "subtract", "multiply", "divide"} and len(args) == 2:
        a, b = args
        if operation == "divide" and b == 0:
            raise MissingEvidence("Division by zero")
        result = {
            "add": lambda: a + b,
            "subtract": lambda: a - b,
            "multiply": lambda: a * b,
            "divide": lambda: a / b,
        }[operation]()
    else:
        raise ValueError("Unsupported operation or arity: " + str(operation))
    if not _number(result):
        raise MissingEvidence("Nonfinite arithmetic result")
    return result


def predicate(rule, context, left=None):
    # Physical admissibility qualifies this existing scientific outcome; it does
    # not add an extra scored outcome or change the partial-credit denominator.
    for domain in rule.get("scientific_domains", []):
        try:
            value = pointer(context["answer"], domain["path"])
        except (KeyError, MissingEvidence):
            return False
        if not _number(value):
            return False
        if "minimum" in domain and value < domain["minimum"]:
            return False
        if "maximum" in domain and value > domain["maximum"]:
            return False
    if "left" in rule:
        left = operand(rule["left"], context)
    op = rule["op"]
    if op == "exists":
        return True  # Resolving the selector already checked existence; null exists.
    if op == "finite":
        return _number(left)
    if op == "type":
        types = {
            "number": _number,
            # JSON numbers such as6.0 are integral; Booleans and near-integers
            # are not counts. Type checks never borrow numeric tolerances.
            "integer": lambda v: _number(v) and int(v) == v,
            "string": lambda v: isinstance(v, str),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
            "boolean": lambda v: type(v) is bool,
            "null": lambda v: v is None,
        }
        if not isinstance(rule.get("value"), str) or rule["value"] not in types:
            raise MissingEvidence("Unknown evidence type")
        return types[rule["value"]](left)
    right = operand(rule.get("right", {"value": rule.get("value")}), context)
    if _contains_nonfinite(left) or _contains_nonfinite(right):
        return False
    equal = lambda a, b: _equal(
        a, b, rule.get("atol", 0), rule.get("rtol", 0), rule.get("casefold", False)
    )
    if op == "curve_equivalent":
        return _curve_equivalent(left, right, rule)
    if op == "eq":
        return equal(left, right)
    if op == "ne":
        return not equal(left, right)
    if op in {"lt", "le", "gt", "ge"}:
        if not _number(left) or not _number(right):
            return False
        return {
            "lt": left < right,
            "le": left <= right,
            "gt": left > right,
            "ge": left >= right,
        }[op]
    if op == "one_of":
        return isinstance(right, list) and any(equal(left, value) for value in right)
    if op in {"set_equal", "multiset_equal"}:
        return _unordered(left, right, rule, deduplicate=op == "set_equal")
    if op == "subset":
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and all(any(equal(a, b) for b in right) for a in left)
        )
    raise ValueError("Unsupported predicate " + str(op))
