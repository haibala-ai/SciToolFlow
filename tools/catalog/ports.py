"""Validate documented data ports used for candidate graph expansion.

Concept equality suggests a candidate transfer. It never establishes compatible
units, scientific methods, identities, pagination completeness or execution.
"""


def _nodes(schema, path):
    if not isinstance(schema, dict):
        return []
    if not path:
        return [schema]
    nodes = []
    for family in ("anyOf", "oneOf", "allOf"):
        for branch in schema.get(family, []):
            nodes.extend(_nodes(branch, path))
    head, *tail = path
    if head == "*":
        if isinstance(schema.get("items"), dict):
            nodes.extend(_nodes(schema["items"], tail))
        if isinstance(schema.get("additionalProperties"), dict):
            nodes.extend(_nodes(schema["additionalProperties"], tail))
    elif type(head) is int and head >= 0:
        prefix = schema.get("prefixItems", [])
        if head < len(prefix):
            nodes.extend(_nodes(prefix[head], tail))
        elif isinstance(schema.get("items"), dict):
            nodes.extend(_nodes(schema["items"], tail))
    elif head in schema.get("properties", {}):
        nodes.extend(_nodes(schema["properties"][head], tail))
    return nodes


def validate_ports(name, spec):
    """Reject undeclared inputs, imaginary output fields and wrong wire decoding."""
    dataflow = spec.get("dataflow")
    if not isinstance(dataflow, dict):
        raise ValueError(name + ": missing dataflow declaration")
    for direction in ("inputs", "outputs"):
        ports = dataflow.get(direction)
        if not isinstance(ports, list):
            raise ValueError(name + ": dataflow ports must be arrays")
        for port in ports:
            if not isinstance(port.get("concept"), str) or not port["concept"].strip():
                raise ValueError(name + ": empty data concept")
            if direction == "inputs":
                if port.get("parameter") not in spec["input_schema"]["properties"]:
                    raise ValueError(name + ": undeclared input port " + str(port))
                continue
            path = port.get("path")
            if not isinstance(path, list) or any(
                not isinstance(part, str) and not (type(part) is int and part >= 0)
                for part in path
            ):
                raise ValueError(name + ": invalid output field path")
            schema = spec["output_schema"]
            if port.get("decoded"):
                encoding = spec.get("output_encoding", {})
                if schema.get("type") != "string" or encoding.get(
                    "decoded_type"
                ) not in {"json_object", "json_array"}:
                    raise ValueError(
                        name + ": decoded port on a non-JSON-string output"
                    )
                schema = encoding.get("decoded_schema", {})
            if not _nodes(schema, path):
                raise ValueError(
                    name + ": output port not declared in schema: " + str(path)
                )
    return True
