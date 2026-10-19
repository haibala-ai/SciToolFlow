"""Real question drafting and restricted-tool ReAct generation, inspired by paper §4.3.

Gold values and reference plans are never supplied to the LLM. The construction
tool subset follows the paper; this generator is not a full-registry evaluation.
"""

import json


def field(value, path):
    """Walk a decoded value by an explicit list of keys.

    Defined here so this package stands alone: the scorer keeps its own copy beside the rest of
    its machinery, and the runtime must not have to reach into the scoring package to parse a reply.
    """
    for key in path:
        value = value[key]
    return value


def parse_reply(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as error:
        raise ValueError(
            "Return exactly one complete JSON object, without surrounding prose"
        ) from None
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def schema(binding):
    if isinstance(binding, dict):
        if any(k.startswith("$") for k in binding):
            return "value or complete tool result"
        return {k: schema(v) for k, v in binding.items()}
    if isinstance(binding, list):
        return [schema(v) for v in binding]
    return "value"


def expand_citations(value, observations):
    if isinstance(value, dict):
        if "$observation" in value:
            if set(value) - {"$observation", "field", "decode"}:
                raise ValueError("Invalid observation citation")
            row = observations.get(value["$observation"])
            if row is None or row["status"] != "success":
                raise ValueError("Citation is not a successful real tool observation")
            result = row["output"]
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except ValueError:
                    pass
            result = field(result, value.get("field", []))
            if "decode" in value:
                if value["decode"] != "json_array":
                    raise ValueError("Unknown observation decoder")
                result = decode_observed_array(result)
            return result
        return {k: expand_citations(v, observations) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_citations(v, observations) for v in value]
    return value


def decode_observed_array(value):
    """Extract one literal JSON array from a returned text, with no computation.

    Scientific Markdown adapters often embed a complete native vector. Passing
    that exact vector need not consume a model completion to retype its entries.
    Multiple separate arrays are ambiguous and require an explicit tool/parser.
    """
    if isinstance(value, list):
        json.dumps(value, allow_nan=False)
        return value
    if not isinstance(value, str) or len(value.encode()) > 1_000_000:
        raise ValueError("Array decoding requires bounded observed text or an array")
    start = value.find("[")
    if start < 0:
        raise ValueError("No complete literal JSON array in observed text")
    try:
        array, end = json.JSONDecoder().raw_decode(value, start)
    except ValueError:
        raise ValueError("Incomplete or non-JSON observed array") from None
    if not isinstance(array, list):
        raise ValueError("Observed value is not an array")
    if "[" in value[end:]:
        raise ValueError("Ambiguous multiple observed arrays")
    # Reject non-finite extension literals accepted by Python's JSON decoder.
    json.dumps(array, allow_nan=False)
    return array
