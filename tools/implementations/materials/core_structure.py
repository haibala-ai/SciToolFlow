"""Complete validated material-core geometry, with no property-task fallback."""

from tools.implementations.shared.materials_api import (
    get as mp_get, MissingScientificData, response_payload,
)


def get_structure_by_material_id(material_id: str) -> dict:
    """Get one final core crystal structure for a single Materials Project ID.

    Queries only the official materials/core endpoint; this is its current
    final material structure, not necessarily the geometry of another property
    calculation or a surface slab. Legacy numeric mp-/mvc- IDs and current
    eight-letter mp- IDs are accepted. Aliases are reported as requested and
    resolved IDs. No fallback to another property endpoint is performed.
    Args:
        material_id (str): One bare legal material ID; no list, formula or query.
    Returns:
        dict: Complete original Structure JSON (all species and occupancies
        retained), resolved/requested material IDs, source hash and provenance. Cell
        lengths/angles/volume and fractional/Cartesian coordinates are checked
        with roundoff tolerances. Site coordinates may differ by integer cell
        images only along periodic axes (pbc defaults to all true if absent).
        Missing, ambiguous, malformed, authorization or HTTP responses raise
        explicit exceptions; no None or fabricated structure is returned.
    """
    import hashlib
    import json
    import math
    import re

    if not isinstance(material_id, str):
        raise ValueError("material_id must be one bare Materials Project ID")
    requested = material_id.strip()
    if not re.fullmatch(r"(?:mp-(?:\d{1,18}|[a-z]{8})|mvc-\d{1,18})", requested):
        raise ValueError("Expected one mp- numeric/eight-letter or mvc- numeric material ID; lists and queries are not accepted")
    endpoint = "https://api.materialsproject.org/materials/core/"
    response = mp_get(
        endpoint,
        headers={"accept": "application/json", "Content-Type": "application/json"},
        params={"material_ids": requested, "_limit": 2,
                "_fields": "material_id,structure,last_updated", "_all_fields": "false"},
    )
    if response.status_code != 200:
        raise RuntimeError("Materials Project core structure HTTP " + str(response.status_code))
    try:
        payload = response_payload(response)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Materials Project core structure response is not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("Materials Project core structure response has no record array")
    records = payload["data"]
    if not records:
        raise MissingScientificData("No core structure for material " + requested)
    if len(records) != 1:
        raise RuntimeError("Materials Project core structure query returned multiple records for one ID")
    record = records[0]
    if not isinstance(record, dict) or not isinstance(record.get("material_id"), str) or not re.fullmatch(r"(?:mp-(?:\d{1,18}|[a-z]{8})|mvc-\d{1,18})", record["material_id"]):
        raise RuntimeError("Materials Project core structure record has no resolved material ID")
    structure = record.get("structure")
    if not isinstance(structure, dict):
        raise MissingScientificData("Core structure is not published for material " + requested)
    try:
        # This validates serialization without changing the original source
        # species, occupancies, coordinates, properties or numeric values.
        raw_structure = json.dumps(structure, ensure_ascii=False, allow_nan=False, sort_keys=True)
        lattice, sites = structure["lattice"], structure["sites"]
        if not isinstance(lattice, dict) or not isinstance(sites, list) or not 1 <= len(sites) <= 10000:
            raise ValueError("Expected lattice object and 1..10000 sites")
        for field in ["a", "b", "c", "alpha", "beta", "gamma", "volume"]:
            value = lattice[field]
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid positive lattice field " + field)
        matrix = lattice["matrix"]
        if not isinstance(matrix, list) or len(matrix) != 3 or any(not isinstance(row, list) or len(row) != 3 for row in matrix):
            raise ValueError("Lattice matrix must be 3x3")
        if any(type(v) not in (int, float) or not math.isfinite(v) for row in matrix for v in row):
            raise ValueError("Lattice matrix contains nonfinite/non-numeric components")
        determinant = (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )
        if not math.isfinite(determinant) or determinant == 0 or not math.isclose(abs(determinant), lattice["volume"], rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError("Lattice matrix determinant contradicts its positive volume")
        if any(lattice[angle] >= 180 for angle in ["alpha", "beta", "gamma"]):
            raise ValueError("Lattice angles must be strictly between 0 and 180 degrees")
        lengths = [math.hypot(*row) for row in matrix]
        if any(not math.isfinite(length) or length <= 0 for length in lengths):
            raise ValueError("Lattice matrix row lengths must be positive and finite")
        if any(not math.isclose(length, lattice[key], rel_tol=1e-5, abs_tol=1e-6) for length, key in zip(lengths, ["a", "b", "c"])):
            raise ValueError("Lattice a/b/c contradict matrix row lengths")
        for key, i, j in [("alpha", 1, 2), ("beta", 0, 2), ("gamma", 0, 1)]:
            cosine = sum((matrix[i][k] / lengths[i]) * (matrix[j][k] / lengths[j]) for k in range(3))
            actual_angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
            if not math.isclose(actual_angle, lattice[key], rel_tol=1e-6, abs_tol=1e-3):
                raise ValueError("Lattice " + key + " contradicts matrix row angle")
        periodic = lattice.get("pbc", [True, True, True])
        if not isinstance(periodic, list) or len(periodic) != 3 or any(type(v) is not bool for v in periodic):
            raise ValueError("Lattice pbc must contain three booleans")
        def cross(left, right):
            return [left[1] * right[2] - left[2] * right[1], left[2] * right[0] - left[0] * right[2], left[0] * right[1] - left[1] * right[0]]
        reciprocal = [cross(matrix[1], matrix[2]), cross(matrix[2], matrix[0]), cross(matrix[0], matrix[1])]
        coordinate_tolerance = max(1e-5, 1e-6 * max(lengths))
        for site in sites:
            if not isinstance(site, dict) or not isinstance(site.get("species"), list) or not site["species"]:
                raise ValueError("Missing complete site species array")
            occupancy = 0.0
            for species in site["species"]:
                if not isinstance(species, dict) or not isinstance(species.get("element"), str) or not species["element"]:
                    raise ValueError("Invalid species element")
                fraction = species["occu"]
                if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                    raise ValueError("Invalid species occupancy")
                occupancy += fraction
            if not 0 < occupancy <= 1.000001:
                raise ValueError("Site occupancy sum must be positive and at most one")
            for field in ["abc", "xyz"]:
                vector = site[field]
                if not isinstance(vector, list) or len(vector) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
                    raise ValueError("Invalid site coordinate " + field)
            predicted = [sum(site["abc"][i] * matrix[i][j] for i in range(3)) for j in range(3)]
            delta = [site["xyz"][j] - predicted[j] for j in range(3)]
            fractional_delta = [sum(delta[j] * basis[j] for j in range(3)) / determinant for basis in reciprocal]
            if not all(math.isfinite(v) for v in predicted + delta + fractional_delta):
                raise ValueError("Source coordinate conversion is not finite")
            images = [round(v) if pbc else 0 for v, pbc in zip(fractional_delta, periodic)]
            residual = [delta[j] - sum(images[i] * matrix[i][j] for i in range(3)) for j in range(3)]
            if math.hypot(*residual) > coordinate_tolerance:
                raise ValueError("Site xyz contradicts abc@lattice even after allowed periodic images")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("Malformed Materials Project core Structure: " + str(exc)) from exc
    return {"source_endpoint": endpoint, "requested_material_id": requested,
            "resolved_material_id": record["material_id"], "last_updated": record.get("last_updated"),
            "structure_sha256": hashlib.sha256(raw_structure.encode("utf-8")).hexdigest(),
            "structure_sha256_convention": "UTF-8 JSON with sort_keys=True,ensure_ascii=False,default separators; complete original Structure value",
            "structure_role": "Current final material core structure; not necessarily another property task geometry",
            "structure": structure}
