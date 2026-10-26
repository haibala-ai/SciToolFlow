"""Focused Materials Project primitives with explicit selectors and source identity.

Public functions select one scientific quantity.  The common retrieval helpers
are private and never expose an arbitrary fields/all-properties tool.
"""

import json
import math
import re

from tools.implementations.shared import materials_api
from tools.implementations.shared.materials_api import MissingScientificData

BASE = "https://api.materialsproject.org/"


def _text(value, label, maximum=256):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be nonempty text of at most {maximum} characters")
    value = value.strip()
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} contains control characters")
    return value


def _material_id(value):
    value = _text(value, "material_id")
    if not re.fullmatch(r"(?:mp-(?:\d{1,18}|[a-z]{8})|mvc-\d{1,18})", value):
        raise ValueError("Expected one bare numeric/eight-letter mp- ID or numeric mvc- ID")
    return value


def _molecule_id(value):
    value = _text(value, "molecule_id")
    if not re.fullmatch(r"(?:[A-Za-z]+-)?[A-Fa-f0-9]+-[A-Za-z0-9]+-m?\d+-\d+", value):
        raise ValueError("Expected one Materials Project MPculeID; file paths and lists are not molecule IDs")
    return value


def _battery_id(value):
    value = _text(value, "battery_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Expected one bare insertion-electrode battery ID")
    return value


def _formula(value, molecular=False):
    from pymatgen.core import Composition

    value = _text(value, "formula", 256)
    if any(c in value for c in ",=*?[]{}"):
        raise ValueError("Supply one explicit formula; lists, wildcards and query expressions are unsupported")
    composition = Composition(value, strict=True)
    if not composition or any(not math.isfinite(float(v)) or v <= 0 for v in composition.values()):
        raise ValueError("Formula requires finite positive atom amounts")
    if molecular:
        values = composition.get_el_amt_dict()
        if any(not float(v).is_integer() for v in values.values()):
            raise ValueError("Molecular formula requires positive integer atom counts")
        return " ".join(f"{element}{int(values[element])}" for element in sorted(values))
    return value


def _bounds(offset, limit):
    if type(offset) is not int or not 0 <= offset <= 1000000:
        raise ValueError("offset must be an integer in [0,1000000]")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be an integer in [1,200]")


def _selector(material_id, formula, material_ids=None):
    if sum(value is not None for value in (material_id, formula, material_ids)) != 1:
        raise ValueError("Supply exactly one of material_id, material_ids or formula")
    if material_ids is not None:
        if (not isinstance(material_ids, list) or not 1 <= len(material_ids) <= 200
                or any(not isinstance(v, str) or not re.fullmatch(r"mp-[a-z]{8}", v) for v in material_ids)
                or len(set(material_ids)) != len(material_ids)):
            raise ValueError("material_ids requires 1..200 unique canonical eight-letter mp- IDs; resolve legacy aliases individually first")
        return {"material_ids": ",".join(material_ids)}
    return ({"material_ids": _material_id(material_id)} if material_id is not None
            else {"formula": _formula(formula)})


def _page(route, filters, fields, offset=0, limit=100):
    _bounds(offset, limit)
    params = dict(filters, _skip=offset, _limit=limit + 1)
    if fields is not None:
        params.update(_fields=",".join(dict.fromkeys(fields)), _all_fields="false")
    payload = materials_api.response_payload(materials_api.get(BASE + route, params=params, allow_empty=True))
    records = payload["data"]
    if any(not isinstance(record, dict) for record in records):
        raise RuntimeError("Materials Project returned malformed record entries")
    # Reject invalid JSON numbers throughout nested scientific arrays/objects.
    json.dumps(records, allow_nan=False)
    has_more = len(records) > limit
    metadata = payload.get("meta") or {}
    total = metadata.get("total_doc")
    if type(total) is int and total > offset + len(records[:limit]):
        has_more = True
    return records[:limit], {"offset": offset, "limit": limit, "has_more": has_more,
                            "next_offset": offset + limit if has_more else None,
                            "total_matching_documents": total}, metadata


def _material(field, unit, material_id=None, formula=None, offset=0, limit=100,
              route="materials/summary/", nested=None, material_ids=None):
    selector = _selector(material_id, formula, material_ids)
    if material_id is not None and offset:
        raise ValueError("offset must be zero for a single material_id")
    context = [] if route == "materials/surface_properties/" else ["last_updated", "origins"]
    if route in {"materials/bonds/", "materials/oxidation_states/"}:
        context.append("method")
    filters = dict(selector)
    if route in {"materials/summary/", "materials/core/"}:
        filters["deprecated"] = False
    records, page, meta = _page(route, filters,
        ["material_id", field, *context], offset, limit)
    if material_id is not None and len(records) > 1:
        raise RuntimeError("One material ID resolved to multiple source records")
    observations = []
    for record in records:
        resolved = record.get("material_id")
        if not isinstance(resolved, str) or not resolved:
            raise RuntimeError("Materials Project record omitted resolved material_id")
        if material_ids is not None and resolved not in material_ids:
            raise RuntimeError("Batch response identity does not match the canonical requested-ID set")
        value = record.get(field)
        if nested and isinstance(value, dict):
            value = value.get(nested)
        observations.append({"material_id": resolved, "value": value,
            "available": value is not None, "last_updated": record.get("last_updated"),
            "origins": record.get("origins"), "method": record.get("method")})
    if not observations and offset == 0:
        raise MissingScientificData("No matching Materials Project material records")
    if material_id is not None and observations[0]["value"] is None:
        raise MissingScientificData(f"{field}{'.' + nested if nested else ''} is not published for this material")
    return {"source": BASE + route, "selector": selector, "query_filters": filters,
        "field": field + ("." + nested if nested else ""), "units": unit,
        "records": observations, "pagination": page,
        "missing_requested_ids": (sorted(set(material_ids) - {r["material_id"] for r in observations})
            if material_ids is not None and offset == 0 and not page["has_more"] else None),
        "api_version": meta.get("api_version"), "queried_at": meta.get("time_stamp"),
        "scope": "Published calculation records; formula may match multiple polymorphs. Null values are explicitly unavailable; no value is inferred."}


def _one(route, selector, field, identity=None, context=()):
    fields = [field, "last_updated", *context]
    if identity:
        fields.append(identity)
    records, page, meta = _page(route, selector, fields, 0, 1)
    if not records:
        raise MissingScientificData("No matching Materials Project record")
    if page["has_more"]:
        raise RuntimeError("The supplied identifier matched multiple records; refusing an arbitrary first record")
    record = records[0]
    if field not in record or record[field] is None:
        raise MissingScientificData(f"{field} is not published for the requested record")
    return record, meta


def _battery(field, unit, battery_id):
    requested = _battery_id(battery_id)
    record, meta = _one("materials/insertion_electrodes/", {"battery_ids": requested},
                        field, context=("battery_type", "thermo_type"))
    return {"source": BASE + "materials/insertion_electrodes/",
        "requested_battery_id": requested, "field": field, "units": unit,
        "value": record[field], "last_updated": record.get("last_updated"),
        "battery_type": record.get("battery_type"), "thermo_type": record.get("thermo_type"),
        "api_version": meta.get("api_version"), "queried_at": meta.get("time_stamp"),
        "scope": "Published insertion-electrode record. Aggregate scalar properties are distinct from per-step adj_pairs."}


def _molecule(field, unit, molecule_id, group=None, nested=None):
    requested = _molecule_id(molecule_id)
    record, meta = _one("molecules/summary/", {"molecule_ids": requested}, group or field,
                        identity="molecule_id")
    resolved = record.get("molecule_id")
    if resolved != requested:
        raise RuntimeError("Molecule response identity does not match the requested MPculeID")
    value = record[group or field]
    if group:
        if not isinstance(value, dict):
            raise RuntimeError("Molecule composite is not a solvent-labelled mapping")
        selected = nested or field
        value = {solvent: {"value": item[selected], "level_of_theory": item.get("level_of_theory"),
                           "property_id": item.get("property_id")}
                 for solvent, item in value.items()
                 if isinstance(item, dict) and item.get(selected) is not None}
        if not value:
            raise MissingScientificData(f"{group}.{selected} is not published for this molecule")
    return {"source": BASE + "molecules/summary/", "molecule_id": resolved,
        "field": (group + "." if group else "") + (nested or field), "units": unit,
        "value": value, "solvent_labelled": group is not None,
        "last_updated": record.get("last_updated"), "api_version": meta.get("api_version"),
        "queried_at": meta.get("time_stamp"),
        "scope": "Published molecule calculation data. Solvent-labelled method/property identity is retained; missing fields are never replaced by total/global values."}


def _qchem(field, qchem_file):
    from tools.implementations.shared.qchem_details import extract_property

    path = _text(qchem_file, "qchem_file", 4096)
    if path.startswith("qchem:"):
        raise ValueError("qchem_file is a file path; omit the legacy qchem: prefix")
    return json.loads(extract_property("qchem:" + path, field))


def resolve_charge_density_metadata(task_id: str = None, fs_id: str = None) -> dict:
    """Resolve one verified historical CHGCAR task/file/URL relationship.

    Supply exactly one task_id or 24-hex fs_id. Forward lookup reads an official
    envelope; reverse lookup uses verified cache/legacy-object headers. Coverage
    is incomplete and asymmetric. Returns dated provenance, not density arrays.
    """
    from tools.implementations.shared.charge_density_metadata import metadata_for_task, metadata_for_file

    if (task_id is None) == (fs_id is None):
        raise ValueError("Supply exactly one of task_id or fs_id")
    return metadata_for_task(_text(task_id, "task_id")) if task_id is not None else metadata_for_file(_text(fs_id, "fs_id"))


def get_material_description(material_id: str = None, keywords: str = None,
                             offset: int = 0, limit: int = 20) -> dict:
    """Retrieve published robocrys text by one material ID or keyword query.

    Returns descriptions and resolved IDs with explicit pagination. Does not
    generate a new description or expose other material physical properties.
    """
    if (material_id is None) == (keywords is None):
        raise ValueError("Supply exactly one of material_id or keywords")
    if material_id is not None:
        if offset:
            raise ValueError("offset must be zero for material_id lookup")
        route, selector = "materials/robocrys/", {"material_ids": _material_id(material_id)}
        fields = ["material_id", "description", "last_updated"]
    else:
        route, selector = "materials/robocrys/text_search/", {"keywords": _text(keywords, "keywords", 512)}
        fields = None
    records, page, meta = _page(route, selector, fields, offset, limit)
    return {"source": BASE + route, "selector": selector,
            "records": [{"material_id": r.get("material_id"), "description": r.get("description"),
                         "available": r.get("description") is not None} for r in records],
            "pagination": page, "api_version": meta.get("api_version")}


def search_materials(formula: str = None, elements: list = None, chemsys: str = None,
                     band_gap_min: float = None, band_gap_max: float = None,
                     is_stable: bool = None, offset: int = 0, limit: int = 50) -> dict:
    """Discover material IDs by explicit composition/electronic filters.

    Elements is contains-all; chemsys is an exact element system. At least one
    filter is required. Stability is never silently imposed. Returns IDs only,
    with pagination; obtain each distinct property through its focused tool.
    """
    from pymatgen.core import Element

    filters = {}
    if formula is not None:
        filters["formula"] = _formula(formula)
    if elements is not None:
        if not isinstance(elements, list) or not 1 <= len(elements) <= 10:
            raise ValueError("elements must be a unique list of 1..10 element symbols")
        if any(not isinstance(v, str) or not Element.is_valid_symbol(v) for v in elements):
            raise ValueError("elements contains an invalid element symbol")
        if len(set(elements)) != len(elements):
            raise ValueError("elements must not contain duplicate symbols")
        filters["elements"] = ",".join(elements)
    if chemsys is not None:
        value = _text(chemsys, "chemsys", 60)
        symbols = value.split("-")
        if len(set(symbols)) != len(symbols) or any(not Element.is_valid_symbol(v) for v in symbols):
            raise ValueError("chemsys requires unique element symbols separated by hyphens")
        filters["chemsys"] = "-".join(sorted(symbols))
    for label, value in [("band_gap_min", band_gap_min), ("band_gap_max", band_gap_max)]:
        if value is not None:
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                raise ValueError(label + " must be finite and nonnegative, in eV")
            filters[label] = value
    if band_gap_min is not None and band_gap_max is not None and band_gap_min > band_gap_max:
        raise ValueError("band_gap_min must not exceed band_gap_max")
    if is_stable is not None:
        if type(is_stable) is not bool:
            raise ValueError("is_stable must be a boolean or null")
        filters["is_stable"] = is_stable
    if not filters:
        raise ValueError("Supply at least one search filter")
    records, page, meta = _page("materials/summary/", filters, ["material_id"], offset, limit)
    if any(not isinstance(r.get("material_id"), str) for r in records):
        raise RuntimeError("Material search omitted record identity")
    return {"source": BASE + "materials/summary/", "filters": filters,
            "material_ids": [r["material_id"] for r in records], "pagination": page,
            "api_version": meta.get("api_version"), "queried_at": meta.get("time_stamp")}


def get_molecule_id_by_formula(formula: str, offset: int = 0, limit: int = 100) -> dict:
    """Find MPculeIDs for an explicit integer-count molecular formula; retain all charge/spin isomers in a page."""
    value = _formula(formula, molecular=True)
    records, page, meta = _page("molecules/summary/", {"formula": value}, ["molecule_id"], offset, limit)
    if any(not isinstance(r.get("molecule_id"), str) for r in records):
        raise RuntimeError("Molecule search omitted record identity")
    return {"source": BASE + "molecules/summary/", "formula_alphabetical": value,
            "molecule_ids": [r["molecule_id"] for r in records], "pagination": page,
            "api_version": meta.get("api_version")}


def get_material_deprecation_status(material_id: str) -> dict:
    """Read the core material's actual deprecated boolean, never a battery status or reasons list."""
    requested = _material_id(material_id)
    # Core's default filter excludes deprecated records. An empty first query is
    # not evidence of false status; explicitly inspect the other population.
    for state in (False, True):
        filters = {"material_ids": requested, "deprecated": state}
        records, page, meta = _page("materials/core/", filters,
            ["material_id", "deprecated", "last_updated", "origins"], 0, 1)
        if not records:
            continue
        if page["has_more"] or len(records) != 1:
            raise RuntimeError("Material deprecation lookup is ambiguous")
        record = records[0]
        if type(record.get("deprecated")) is not bool or not isinstance(record.get("material_id"), str):
            raise RuntimeError("Core record has no explicit identity/deprecated boolean")
        return {"source": BASE + "materials/core/", "selector": {"material_ids": requested},
            "query_filters": filters, "field": "deprecated", "units": "boolean",
            "records": [{"material_id": record["material_id"], "value": record["deprecated"],
                         "available": True, "last_updated": record.get("last_updated"),
                         "origins": record.get("origins"), "method": None}],
            "pagination": page, "api_version": meta.get("api_version"),
            "queried_at": meta.get("time_stamp"),
            "scope": "Actual core material status; false/true populations queried explicitly as needed. No reasons list is inferred."}
    raise MissingScientificData("No core material record in either deprecation population")


def get_material_xas_spectrum(formula: str, absorbing_element: str,
                              offset: int = 0, limit: int = 10) -> dict:
    """Retrieve published K-edge XAS records by explicit formula and absorber; no XRD or new spectroscopy calculation."""
    from pymatgen.core import Element

    value = _formula(formula)
    if not isinstance(absorbing_element, str) or not Element.is_valid_symbol(absorbing_element):
        raise ValueError("absorbing_element must be one element symbol")
    records, page, meta = _page("materials/xas/", {"formula": value, "absorbing_element": absorbing_element,
                              "edge": "K"}, ["task_id", "spectrum_name", "spectrum", "spectrum_type",
                              "absorbing_element", "edge", "last_updated", "formula_pretty"], offset, limit)
    if any(r.get("spectrum") is None or r.get("task_id") is None for r in records):
        raise MissingScientificData("XAS record omitted spectrum or calculation identity")
    return {"source": BASE + "materials/xas/", "formula": value,
            "absorbing_element": absorbing_element, "edge": "K", "records": records,
            "pagination": page, "api_version": meta.get("api_version")}


def get_alloy_pairs_by_material_id(material_id: str, offset: int = 0, limit: int = 50) -> dict:
    """Retrieve alloy-pair relationships involving one material; pair_id accompanies each pair, with explicit pagination."""
    selector = {"material_ids": _material_id(material_id)}
    records, page, meta = _page("materials/alloys/", selector, ["pair_id", "alloy_pair"], offset, limit)
    if any(r.get("pair_id") is None or r.get("alloy_pair") is None for r in records):
        raise MissingScientificData("Alloy result omitted its pair identity or relationship")
    return {"source": BASE + "materials/alloys/", "selector": selector,
            "records": records, "pagination": page, "api_version": meta.get("api_version")}


def get_eos_info_by_material_id(material_id: str, offset: int = 0, limit: int = 100) -> dict:
    """Retrieve EOS energies/volumes/fits only for tasks belonging to one core material. No new EOS fit or unrelated task substitution."""
    requested = _material_id(material_id)
    core, _ = _one("materials/core/", {"material_ids": requested}, "task_ids", identity="material_id")
    tasks = core["task_ids"]
    if not isinstance(tasks, list) or not tasks or any(not isinstance(t, str) for t in tasks):
        raise MissingScientificData("Core material has no published task-ID list")
    records, page, meta = _page("materials/eos/", {"task_ids": ",".join(tasks)},
                               ["task_id", "energies", "volumes", "eos"], offset, limit)
    if any(r.get("task_id") not in tasks for r in records):
        raise RuntimeError("EOS task is not associated with the requested core material")
    return {"source": BASE + "materials/core/ -> materials/eos/", "requested_material_id": requested,
            "resolved_material_id": core.get("material_id"), "task_ids": tasks,
            "energy_units": "eV", "volume_units": "angstrom^3", "records": records,
            "pagination": page, "api_version": meta.get("api_version")}


def get_phonon_info_by_material_id(material_id: str) -> dict:
    """Download published DFPT phonon DOS/bands for a numeric archive material ID; returns THz units, full-data artifacts and download hashes, without new calculation."""
    requested = _text(material_id, "material_id")
    if not re.fullmatch(r"mp-\d{1,18}", requested):
        raise ValueError("DFPT archive requires a numeric mp- material ID; canonical REST alphabetic IDs are not archive keys")
    return json.loads(materials_api.phonon_for_material(requested))


def get_last_updated_time_by_task_id(task_id: str) -> dict:
    """Read materials/tasks last_updated and resolved task identity; this is not a file/object modification timestamp."""
    requested = _text(task_id, "task_id")
    if not re.fullmatch(r"(?:mp-\d{1,18}|[a-z]{1,12})", requested):
        raise ValueError("Expected a bare numeric mp-task ID or alphabetical task ID")
    return json.loads(materials_api.task_last_updated(requested))


def get_synthesis_doc_by_keywords(keywords: str, offset: int = 0, limit: int = 10) -> dict:
    """Search published synthesis paragraphs/operations by keywords with DOI/source data and pagination; not an executable synthesis plan or laboratory action."""
    value = _text(keywords, "keywords", 512)
    records, page, meta = _page("materials/synthesis/", {"keywords": value}, None, offset, limit)
    return {"source": BASE + "materials/synthesis/", "keywords": value,
            "records": records, "pagination": page, "api_version": meta.get("api_version")}


def get_molecular_frequencies(molecule_id: str = None, qchem_file: str = None) -> dict:
    """Read signed molecular frequencies in cm^-1 from one MPculeID or explicit completed Q-Chem output. Sources remain distinct; no MP identity is inferred for a file. Positive frequencies alone do not establish optimization convergence or a global minimum."""
    if (molecule_id is None) == (qchem_file is None):
        raise ValueError("Supply exactly one of molecule_id or qchem_file")
    return (_qchem("frequencies", qchem_file) if qchem_file is not None
            else _molecule("frequencies", "cm^-1", molecule_id, group="vibration"))

def get_material_band_gap(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published electronic band gap by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('band_gap', 'eV', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_cbm(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published conduction-band minimum energy by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('cbm', 'eV', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_density_atomic(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read atomic packing volume (cell volume per site, not mass/number density) by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('density_atomic', 'angstrom^3/atom', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_density(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read calculated periodic-cell mass density by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('density', 'g/cm^3', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_e_electronic(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read electronic relative dielectric contribution, not electronic energy by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('e_electronic', 'dimensionless', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_e_ionic(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read ionic relative dielectric contribution, not ionic energy by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('e_ionic', 'dimensionless', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_e_total(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read total relative dielectric permittivity, not total energy by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('e_total', 'dimensionless', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_efermi(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published Fermi energy by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('efermi', 'eV', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_energy_per_atom(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read corrected DFT energy per atom by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('energy_per_atom', 'eV/atom', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_formation_energy_per_atom(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read formation energy per atom relative to elemental references by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('formation_energy_per_atom', 'eV/atom', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_formula_anonymous(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read anonymous stoichiometric formula; elemental identities are deliberately removed by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('formula_anonymous', None, material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_initial_structures(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read initial calculation structures, distinct from the final material core structure by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('initial_structures', 'angstrom', material_id, formula, offset, limit, route='materials/core/', material_ids=material_ids)


def get_material_vbm(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published valence-band maximum energy by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('vbm', 'eV', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_volume(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read calculation-cell volume by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('volume', 'angstrom^3', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_is_magnetic(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published magnetic classification by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('is_magnetic', 'boolean', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_is_metal(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published metallic classification by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('is_metal', 'boolean', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_is_stable(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read published convex-hull stability classification; not thermal/solvent stability by exactly one material_id, canonical material_ids batch, or formula selector. Returns one explicitly identified observation per polymorph with availability and pagination; no implicit first match."""
    return _material('is_stable', 'boolean', material_id, formula, offset, limit, route='materials/summary/', material_ids=material_ids)


def get_material_formula(material_id: str = None, formula: str = None, offset: int = 0, limit: int = 100, material_ids: list = None) -> dict:
    """Read the published pretty formula from the canonical material summary by exactly one ID, canonical ID batch, or formula, retaining each resolved material ID."""
    return _material('formula_pretty', None, material_id, formula, offset, limit, material_ids=material_ids)


def get_energy_above_hull_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published energy_above_hull observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('energy_above_hull', 'eV/atom', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_equilibrium_reaction_energy_per_atom(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published equilibrium_reaction_energy_per_atom observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('equilibrium_reaction_energy_per_atom', 'eV/atom', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_num_magnetic_sites_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published num_magnetic_sites observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('num_magnetic_sites', 'sites', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_total_magnetization_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published total_magnetization observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('total_magnetization', 'mu_B', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_total_magnetization_normalized_formula_units_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published total_magnetization_normalized_formula_units observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('total_magnetization_normalized_formula_units', 'mu_B/formula_unit', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_total_magnetization_normalized_vol_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published total_magnetization_normalized_vol observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('total_magnetization_normalized_vol', 'mu_B/angstrom^3', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_uncorrected_energy_per_atom_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published uncorrected_energy_per_atom observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('uncorrected_energy_per_atom', 'eV/atom', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_composition_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published composition observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('composition', 'atoms per supplied calculation cell', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_nsites_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published nsites observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('nsites', 'sites', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_elements_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published elements observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('elements', None, material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_number_of_elements_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published nelements observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('nelements', 'distinct elements', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_chemical_system_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published chemsys observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('chemsys', None, material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_symmetry_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published symmetry observation from materials/summary/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('symmetry', 'source-reported space/point groups and symprec', material_id=material_id, route='materials/summary/', material_ids=material_ids)


def get_surface_anisotropy_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published surface_anisotropy observation from materials/surface_properties/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('surface_anisotropy', 'dimensionless', material_id=material_id, route='materials/surface_properties/', material_ids=material_ids)


def get_weighted_surface_energy_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published weighted_surface_energy observation from materials/surface_properties/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('weighted_surface_energy', 'J/m^2', material_id=material_id, route='materials/surface_properties/', material_ids=material_ids)


def get_possible_species_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published possible_species observation from materials/oxidation_states/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('possible_species', None, material_id=material_id, route='materials/oxidation_states/', material_ids=material_ids)


def get_possible_valences_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published possible_valences observation from materials/oxidation_states/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('possible_valences', 'oxidation state', material_id=material_id, route='materials/oxidation_states/', material_ids=material_ids)


def get_average_oxidation_states_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published average_oxidation_states observation from materials/oxidation_states/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('average_oxidation_states', 'oxidation state', material_id=material_id, route='materials/oxidation_states/', material_ids=material_ids)


def get_created_time_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published created_at observation from materials/provenance/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('created_at', 'ISO8601 timestamp', material_id=material_id, route='materials/provenance/', material_ids=material_ids)


def get_references_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published references observation from materials/provenance/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('references', None, material_id=material_id, route='materials/provenance/', material_ids=material_ids)


def get_authors_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published authors observation from materials/provenance/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('authors', None, material_id=material_id, route='materials/provenance/', material_ids=material_ids)


def get_remarks_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published remarks observation from materials/provenance/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('remarks', None, material_id=material_id, route='materials/provenance/', material_ids=material_ids)


def get_bond_types_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published bond_types observation from materials/bonds/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('bond_types', None, material_id=material_id, route='materials/bonds/', material_ids=material_ids)


def get_bond_length_stats_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published bond_length_stats observation from materials/bonds/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('bond_length_stats', 'angstrom; variance angstrom^2', material_id=material_id, route='materials/bonds/', material_ids=material_ids)


def get_coordination_envs_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published coordination_envs observation from materials/bonds/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('coordination_envs', None, material_id=material_id, route='materials/bonds/', material_ids=material_ids)


def get_coordination_envs_anonymous_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published coordination_envs_anonymous observation from materials/bonds/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('coordination_envs_anonymous', None, material_id=material_id, route='materials/bonds/', material_ids=material_ids)


def get_structure_graph_by_material_id(material_id: str = None, material_ids: list = None) -> dict:
    """Read only the published structure_graph observation from materials/bonds/ for one material ID or a canonical material_ids batch. Returns resolved IDs, exact values, units and source method/provenance. Single-ID missing data raises; batch missing values are explicitly unavailable. No other property document is substituted."""
    return _material('structure_graph', 'source graph periodic image edges/weights', material_id=material_id, route='materials/bonds/', material_ids=material_ids)


def get_adj_pairs_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode adj_pairs field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('adj_pairs', None, battery_id)


def get_average_voltage_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode average_voltage field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('average_voltage', 'V', battery_id)


def get_battery_formula_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode battery_formula field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('battery_formula', None, battery_id)


def get_capacity_grav_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode capacity_grav field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('capacity_grav', 'mAh/g', battery_id)


def get_capacity_vol_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode capacity_vol field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('capacity_vol', 'mAh/cm^3', battery_id)


def get_chemsys_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode chemsys field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('chemsys', None, battery_id)


def get_electrode_object_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode electrode_object field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('electrode_object', None, battery_id)


def get_elements_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode elements field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('elements', None, battery_id)


def get_energy_grav_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode energy_grav field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('energy_grav', 'Wh/kg', battery_id)


def get_energy_volume_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode energy_vol field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('energy_vol', 'Wh/L', battery_id)


def get_entries_composition_summary_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode entries_composition_summary field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('entries_composition_summary', None, battery_id)


def get_formula_anonymous_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode formula_anonymous field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('formula_anonymous', None, battery_id)


def get_formula_charge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode formula_charge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('formula_charge', None, battery_id)


def get_formula_discharge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode formula_discharge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('formula_discharge', None, battery_id)


def get_fracA_charge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode fracA_charge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('fracA_charge', 'atomic fraction', battery_id)


def get_framework_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode framework field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('framework', None, battery_id)


def get_framework_formula_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode framework_formula field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('framework_formula', None, battery_id)


def get_host_structure_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode host_structure field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('host_structure', None, battery_id)


def get_id_charge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode id_charge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('id_charge', None, battery_id)


def get_id_discharge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode id_discharge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('id_discharge', None, battery_id)


def get_material_id_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode material_ids field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('material_ids', None, battery_id)


def get_max_delta_volume_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode max_delta_volume field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('max_delta_volume', 'dimensionless max(volume)/min(volume)-1; multiply by100 for percent', battery_id)


def get_max_voltage_step_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode max_voltage_step field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('max_voltage_step', 'V', battery_id)


def get_nelements_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode nelements field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('nelements', None, battery_id)


def get_stability_charge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode stability_charge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('stability_charge', 'eV/atom', battery_id)


def get_stability_discharge_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode stability_discharge field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('stability_discharge', 'eV/atom', battery_id)


def get_warnings_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode warnings field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('warnings', None, battery_id)


def get_working_ion_by_battery_id(battery_id: str) -> dict:
    """Read the insertion-electrode working_ion field for one battery ID. Preserve aggregate versus step data and charged/discharged state; no material-ID substitution. Missing fields raise explicitly."""
    return _battery('working_ion', None, battery_id)


def read_qchem_translational_enthalpy(qchem_file: str) -> dict:
    """Parse translational_enthalpy from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('translational_enthalpy', qchem_file)


def read_qchem_translational_entropy(qchem_file: str) -> dict:
    """Parse translational_entropy from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('translational_entropy', qchem_file)


def read_qchem_rotational_enthalpy(qchem_file: str) -> dict:
    """Parse rotational_enthalpy from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('rotational_enthalpy', qchem_file)


def read_qchem_rotational_entropy(qchem_file: str) -> dict:
    """Parse rotational_entropy from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('rotational_entropy', qchem_file)


def read_qchem_vibrational_enthalpy(qchem_file: str) -> dict:
    """Parse vibrational_enthalpy from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('vibrational_enthalpy', qchem_file)


def read_qchem_vibrational_entropy(qchem_file: str) -> dict:
    """Parse vibrational_entropy from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('vibrational_entropy', qchem_file)


def read_qchem_frequency_modes(qchem_file: str) -> dict:
    """Parse frequency_modes from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('frequency_modes', qchem_file)


def read_qchem_ir_intensities(qchem_file: str) -> dict:
    """Parse ir_intensities from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('ir_intensities', qchem_file)


def read_qchem_ir_activities(qchem_file: str) -> dict:
    """Parse printed IR YES/NO activity flags from an explicitly supplied completed Q-Chem output, retaining original units/source hash and calculation provenance. Flags are verified against mode columns, not inferred from intensities; YES remains YES at zero intensity. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('ir_activities', qchem_file)


def read_qchem_nbo_population(qchem_file: str) -> dict:
    """Parse NBO natural-population tables from an explicitly supplied completed Q-Chem output, retaining original columns/source hash and calculation provenance. Combined/alpha/beta tables remain separate; labels come from source headings and are never inferred from electron totals. This field is not published by the current MP summary composite; no MP lookup or new calculation is claimed."""
    return _qchem('nbo_population', qchem_file)


def get_charge_by_molecule_id(molecule_id: str) -> dict:
    """Read the published charge molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('charge', 'elementary charge', molecule_id, group=None)


def get_chemsys_by_molecule_id(molecule_id: str) -> dict:
    """Read the published chemsys molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('chemsys', None, molecule_id, group=None)


def get_composition_by_molecule_id(molecule_id: str) -> dict:
    """Read the published composition molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('composition', None, molecule_id, group=None)


def get_constituent_molecules_by_molecule_id(molecule_id: str) -> dict:
    """Read the published constituent_molecules molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('constituent_molecules', None, molecule_id, group=None)


def get_coord_hash_by_molecule_id(molecule_id: str) -> dict:
    """Read the published coord_hash molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('coord_hash', None, molecule_id, group=None)


def get_deprecated_by_molecule_id(molecule_id: str) -> dict:
    """Read the published deprecated molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('deprecated', None, molecule_id, group=None)


def get_deprecation_reasons_by_molecule_id(molecule_id: str) -> dict:
    """Read the published deprecation_reasons molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('deprecation_reasons', None, molecule_id, group=None)


def get_molecular_electronic_energy(molecule_id: str) -> dict:
    """Read the published thermo.electronic_energy molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('electronic_energy', 'eV', molecule_id, group='thermo')


def get_elements_by_molecule_id(molecule_id: str) -> dict:
    """Read the published elements molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('elements', None, molecule_id, group=None)


def get_formula_alphabetical_by_molecule_id(molecule_id: str) -> dict:
    """Read the published formula_alphabetical molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('formula_alphabetical', None, molecule_id, group=None)


def get_formula_anonymous_by_molecule_id(molecule_id: str) -> dict:
    """Read the published formula_anonymous molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('formula_anonymous', None, molecule_id, group=None)


def get_formula_pretty_by_molecule_id(molecule_id: str) -> dict:
    """Read the published formula_pretty molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('formula_pretty', None, molecule_id, group=None)


def get_free_energy_by_molecule_id(molecule_id: str) -> dict:
    """Read the published thermo.free_energy molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('free_energy', 'eV', molecule_id, group='thermo')


def get_inchi_by_molecule_id(molecule_id: str) -> dict:
    """Read the published inchi molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('inchi', None, molecule_id, group=None)


def get_inchikey_by_molecule_id(molecule_id: str) -> dict:
    """Read the published inchi_key molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('inchi_key', None, molecule_id, group=None)


def get_last_updated_time_by_molecule_id(molecule_id: str) -> dict:
    """Read the published last_updated molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('last_updated', None, molecule_id, group=None)


def get_molecule_levels_of_theory_by_molecule_id(molecule_id: str) -> dict:
    """Read the published molecule_levels_of_theory molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('molecule_levels_of_theory', None, molecule_id, group=None)


def get_natoms_by_molecule_id(molecule_id: str) -> dict:
    """Read the published natoms molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('natoms', 'atoms', molecule_id, group=None)


def get_nelectrons_by_molecule_id(molecule_id: str) -> dict:
    """Read the published nelectrons molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('nelectrons', 'electrons', molecule_id, group=None)


def get_nelements_by_molecule_id(molecule_id: str) -> dict:
    """Read the published nelements molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('nelements', None, molecule_id, group=None)


def get_open_shell_by_molecule_id(molecule_id: str) -> dict:
    """Read the published orbitals.open_shell molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('open_shell', None, molecule_id, group='orbitals')


def get_orbitals_levels_of_theory_by_molecule_id(molecule_id: str) -> dict:
    """Read the published orbitals.level_of_theory molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('level_of_theory', None, molecule_id, group='orbitals')


def get_orbitals_property_ids_by_molecule_id(molecule_id: str) -> dict:
    """Read the published orbitals.property_id molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('property_id', None, molecule_id, group='orbitals')


def get_origins_by_molecule_id(molecule_id: str) -> dict:
    """Read the published origins molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('origins', None, molecule_id, group=None)


def get_property_id_by_molecule_id(molecule_id: str) -> dict:
    """Read the published property_id molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('property_id', None, molecule_id, group=None)


def get_property_name_by_molecule_id(molecule_id: str) -> dict:
    """Read the published property_name molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('property_name', None, molecule_id, group=None)


def get_similar_molecules_by_molecule_id(molecule_id: str) -> dict:
    """Read the published similar_molecules molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('similar_molecules', None, molecule_id, group=None)


def get_species_hash_by_molecule_id(molecule_id: str) -> dict:
    """Read the published species_hash molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('species_hash', None, molecule_id, group=None)


def get_spin_multiplicity_by_molecule_id(molecule_id: str) -> dict:
    """Read the published spin_multiplicity molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('spin_multiplicity', None, molecule_id, group=None)


def get_symmetry_by_molecule_id(molecule_id: str) -> dict:
    """Read the published symmetry molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('symmetry', None, molecule_id, group=None)


def get_thermo_levels_of_theory_by_molecule_id(molecule_id: str) -> dict:
    """Read the published thermo.level_of_theory molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('level_of_theory', None, molecule_id, group='thermo')


def get_thermo_property_ids_by_molecule_id(molecule_id: str) -> dict:
    """Read the published thermo.property_id molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('property_id', None, molecule_id, group='thermo')


def get_molecular_thermal_enthalpy(molecule_id: str) -> dict:
    """Read the published thermo.total_enthalpy molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly. This is the published thermal enthalpy contribution at298.15K in eV; electronic_energy is not added and absolute enthalpy is not inferred."""
    return _molecule('total_enthalpy', 'eV', molecule_id, group='thermo')


def get_total_entropy_by_molecule_id(molecule_id: str) -> dict:
    """Read the published thermo.total_entropy molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('total_entropy', 'eV/K', molecule_id, group='thermo')


def get_unique_calc_types_by_molecule_id(molecule_id: str) -> dict:
    """Read the published unique_calc_types molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('unique_calc_types', None, molecule_id, group=None)


def get_unique_levels_of_theory_by_molecule_id(molecule_id: str) -> dict:
    """Read the published unique_levels_of_theory molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('unique_levels_of_theory', None, molecule_id, group=None)


def get_unique_lot_solvents_by_molecule_id(molecule_id: str) -> dict:
    """Read the published unique_lot_solvents molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('unique_lot_solvents', None, molecule_id, group=None)


def get_unique_solvents_by_molecule_id(molecule_id: str) -> dict:
    """Read the published unique_solvents molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('unique_solvents', None, molecule_id, group=None)


def get_unique_task_types_by_molecule_id(molecule_id: str) -> dict:
    """Read the published unique_task_types molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('unique_task_types', None, molecule_id, group=None)


def get_vibration_levels_of_theory_by_molecule_id(molecule_id: str) -> dict:
    """Read the published vibration.level_of_theory molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('level_of_theory', None, molecule_id, group='vibration')


def get_vibration_property_ids_by_molecule_id(molecule_id: str) -> dict:
    """Read the published vibration.property_id molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('property_id', None, molecule_id, group='vibration')


def get_warnings_by_molecule_id(molecule_id: str) -> dict:
    """Read the published warnings molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('warnings', None, molecule_id, group=None)


def get_zero_point_energy_by_molecule_id(molecule_id: str) -> dict:
    """Read the published thermo.zero_point_energy molecule observation. Retains molecule identity and solvent-labelled property/method context; null/absent data raises explicitly."""
    return _molecule('zero_point_energy', 'eV', molecule_id, group='thermo')
