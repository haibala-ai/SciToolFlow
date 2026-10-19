"""Small, structured validation feedback; tool contracts remain on demand."""


def pointer(parts):
    return "".join("/" + str(k).replace("~", "~0").replace("/", "~1") for k in parts)


def required_answer_fields(schema, limit=128):
    """Make only public required names/types readable; never supply answer values."""
    fields = []

    def visit(node, parts):
        if not isinstance(node, dict) or len(fields) >= limit:
            return
        for name in node.get("required", []):
            child = node.get("properties", {}).get(name, {})
            if len(fields) >= limit:
                return
            path = parts + [name]
            fields.append({"path": pointer(path), "type": child.get("type", "any")})
            visit(child, path)
        if node.get("type") == "array":
            visit(node.get("items", {}), parts + ["*"])

    visit(schema, [])
    return fields


def field_locations(value, name):
    paths = []
    remaining = 1000

    def visit(node, parts):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or len(parts) > 20 or len(paths) >= 3:
            return
        if isinstance(node, dict):
            for key, item in node.items():
                if key == name:
                    paths.append(pointer(parts + [key]))
                visit(item, parts + [key])
                if remaining < 0 or len(paths) >= 3:
                    break
        elif isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, parts + [index])
                if remaining < 0 or len(paths) >= 3:
                    break

    visit(value, [])
    return paths[:3]


def schema_issues(validator, value, limit=5):
    issues, seen = [], set()
    for error in validator.iter_errors(value):
        if error.validator == "required" and isinstance(error.instance, dict):
            for name in error.validator_value:
                if name in error.instance:
                    continue
                path = pointer(list(error.absolute_path) + [name])
                if path in seen:
                    continue
                seen.add(path)
                issue = {
                    "path": path,
                    "rule": "required",
                    "message": "Missing required field at this exact path",
                    "expected_type": error.schema.get("properties", {})
                    .get(name, {})
                    .get("type", "any"),
                }
                elsewhere = field_locations(value, name)
                if elsewhere:
                    issue["same_name_at_other_paths"] = elsewhere
                issues.append(issue)
                if len(issues) >= limit:
                    return issues
        else:
            issues.append(
                {
                    "path": pointer(error.absolute_path),
                    "rule": error.validator,
                    "message": error.message[:500],
                }
            )
            if len(issues) >= limit:
                return issues
    return issues


def action_feedback(index, action, error, catalog):
    name = action.get("tool") if isinstance(action, dict) else None
    feedback = {
        "action_index": index,
        "tool": name,
        "status": "rejected",
        "executed": False,
        "error_type": "ActionValidationError",
        "message": str(error)[:1200],
    }
    if isinstance(name, str) and catalog.canonical(name) in catalog.tools:
        # An input error must be recoverable without another documentation turn.
        # These are public tool types, never task/reference values.
        feedback["expected_input_schema"] = catalog.tools[catalog.canonical(name)][
            "input_schema"
        ]
        feedback["suggested_action"] = {
            "tool": "DescribeTools",
            "arguments": {"tools": [catalog.canonical(name)]},
        }
    elif isinstance(name, str) and name.strip():
        unknown = catalog.describe([name])["unknown"]
        suggestions = unknown[0].get("suggestions", []) if unknown else []
        if suggestions:
            feedback["suggested_action"] = {
                "tool": "DescribeTools",
                "arguments": {"tools": suggestions},
            }
        if ":" in name:
            feedback["naming_hint"] = (
                "Discipline labels are not tool-name prefixes. Use an exact name from the catalogue array."
            )
    return feedback
