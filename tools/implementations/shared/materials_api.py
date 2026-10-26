"""Bounded, authenticated requests and explicit molecule schema migration."""

from src.utils.paths import local_root, artifacts_root
import os
import requests
import json
import threading
from pathlib import Path

_TRANSPORT = threading.local()


def _session(key):
    """Reuse HTTP connections within one worker/thread, without caching data."""
    proxy = os.getenv("SCITOOL_MP_USE_PROXY", "0") == "1"
    identity = (key, proxy)
    if getattr(_TRANSPORT, "identity", None) != identity:
        previous = getattr(_TRANSPORT, "session", None)
        if previous is not None:
            previous.close()
        session = requests.Session()
        session.trust_env = proxy
        _TRANSPORT.identity, _TRANSPORT.session = identity, session
    return _TRANSPORT.session


def response_payload(response):
    """Reuse the already validated JSON object, without a second decode."""
    cached = getattr(response, "_scitool_mp_payload", None)
    return cached if isinstance(cached, dict) else response.json()


class MissingScientificData(LookupError):
    """The current service does not publish a requested value for this record."""


class UnavailableScientificEndpoint(LookupError):
    """An upstream scientific data route is unavailable; this is not a result."""


def xas_by_formula(formula_absorbing_element):
    """Use the live XAS schema, which differs from the stable SDK's model."""
    formula, element = formula_absorbing_element.strip(" \"'").split(".")
    if not formula.isalnum() or not element.isalpha():
        raise ValueError("Expected formula.absorbing_element, for example TiO2.Ti")
    payload = get(
        "https://api.materialsproject.org/materials/xas/",
        params={
            "formula": formula,
            "absorbing_element": element,
            "edge": "K",
            "_limit": 20,
            "_all_fields": "true",
        },
    ).json()
    directory = artifacts_root()
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / f"mp_xas_{formula}_{element}.json"
    artifact.write_text(json.dumps(payload, indent=2))
    documents = []
    for record in payload["data"]:
        documents.append(
            {
                key: value
                for key, value in record.items()
                if key not in ["spectrum", "builder_meta"]
            }
        )
    return json.dumps(
        {
            "source": "Materials Project materials/xas",
            "full_spectra": str(artifact),
            "documents": documents,
        }
    )


def get(url, *, headers=None, params=None, timeout=25, allow_empty=False):
    from tools.runtime.config import Config

    key = Config().MP_KEY
    if not key:
        raise UnavailableScientificEndpoint("Materials Project API key is not configured")
    session = _session(key)
    request_headers = dict(headers or {})
    request_headers["X-API-KEY"] = key
    query = dict(params or {})
    if "/molecules/" in url:
        # The live OpenAPI schema no longer accepts this query parameter.
        query.pop("deprecated", None)
    try:
        response = session.get(url, headers=request_headers, params=query, timeout=timeout)
    except requests.RequestException as error:
        # Never expose authenticated request objects or URLs containing inputs.
        raise UnavailableScientificEndpoint("Materials Project transport failed: " + type(error).__name__) from None
    if not response.ok:
        # Avoid requests' exception representation exposing URL query strings.
        if response.status_code == 404:
            raise UnavailableScientificEndpoint(
                f"Materials Project HTTP 404 at {url.split('?')[0]}"
            )
        raise RuntimeError(
            f"Materials Project HTTP {response.status_code} at {url.split('?')[0]}"
        )
    try:
        payload = response.json()
    except (ValueError, TypeError):
        raise RuntimeError("Materials Project response is not valid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("Materials Project response has no record array")
    if payload.get("errors"):
        raise RuntimeError("Materials Project response reports query errors")
    if not payload["data"] and not allow_empty:
        raise MissingScientificData("No matching Materials Project records")
    response._scitool_mp_payload = payload
    return response


def task_last_updated(task_id):
    """Return the task document timestamp, rather than charge-file metadata.

    The published ``materials/tasks`` filter accepts the charge-density file
    naming (``mp-2246557``) and answers with that task document's own legacy
    identifier (``aaaexvib``).  Both identifiers are reported instead of rejecting
    the documented mapping.
    """
    task_id = task_id.strip(" \"'")
    if "=" in task_id:
        task_id = task_id.split("=", 1)[1]
    record = get(
        "https://api.materialsproject.org/materials/tasks/",
        params={
            "task_ids": task_id,
            "_fields": "task_id,last_updated",
            "_limit": 1,
        },
    ).json()["data"][0]
    if not record.get("last_updated"):
        raise MissingScientificData("The task has no published last_updated timestamp")
    canonical = record.get("task_id")
    return json.dumps(
        {
            "source": "Materials Project materials/tasks",
            "requested_task_id": task_id,
            "task_id": canonical,
            "last_updated": record["last_updated"],
            "task_id_mapping": (
                None
                if str(canonical) == task_id
                else f"{task_id} resolves to the task document {canonical}"
            ),
            "scope": "task document, not charge-density file",
        }
    )


def phonon_for_material(material_id):
    """Fetch the official DFPT band structure and DOS objects keyed by material ID."""
    import gzip
    import hashlib
    import math
    import re
    from uuid import uuid4

    material_id = material_id.strip(" \"'")
    if "=" in material_id:
        material_id = material_id.split("=", 1)[1]
    if not re.fullmatch(r"mp-[0-9]+", material_id):
        raise ValueError(
            "Expected a numeric MP material ID supported by the published DFPT object archive"
        )
    # These are the exact object keys used by the official mp-api client.
    # The live REST schema uses phonon identifiers and omits the large arrays.
    payloads, sources = {}, {}
    with requests.Session() as session:
        session.trust_env = os.getenv("SCITOOL_MP_USE_PROXY", "0") == "1"
        for kind, prefix in [
            ("dos", "ph-dos"),
            ("band_structure", "ph-bandstructures"),
        ]:
            url = f"https://materialsproject-parsed.s3.amazonaws.com/{prefix}/dfpt/{material_id}.json.gz"
            response = session.get(url, timeout=25)
            if response.status_code == 404:
                raise MissingScientificData(
                    f"No published DFPT {kind} object for {material_id}"
                )
            if not response.ok:
                raise RuntimeError(
                    f"Materials Project object HTTP {response.status_code} at {url}"
                )
            content = response.content
            if content.startswith(b"\x1f\x8b"):
                content = gzip.decompress(content)
            payloads[kind] = json.loads(content)
            sources[kind] = {
                "url": url,
                "sha256_download": hashlib.sha256(response.content).hexdigest(),
            }
    dos, band = payloads["dos"], payloads["band_structure"]
    frequencies, densities = dos["frequencies"], dos["densities"]
    if not frequencies or len(frequencies) != len(densities):
        raise ValueError("Invalid published phonon DOS array dimensions")
    if not all(
        math.isfinite(value) for values in [frequencies, densities] for value in values
    ):
        raise ValueError("Published phonon DOS contains non-finite values")
    qpoints, branches = band["qpoints"], band["frequencies"]
    if (
        not qpoints
        or not branches
        or any(len(branch) != len(qpoints) for branch in branches)
    ):
        raise ValueError("Invalid published phonon band array dimensions")
    if not all(math.isfinite(value) for branch in branches for value in branch):
        raise ValueError("Published phonon bands contain non-finite values")
    directory = artifacts_root() / f"phonon_{uuid4().hex}"
    directory.mkdir(parents=True)
    artifacts = {}
    for kind, payload in payloads.items():
        target = directory / f"{kind}.json"
        target.write_text(json.dumps(payload))
        artifacts[kind] = str(target)
    return json.dumps(
        {
            "input_material_id": material_id,
            "phonon_method": "dfpt",
            "sources": sources,
            "full_data": artifacts,
            "frequency_units": "THz",
            "dos_points": len(frequencies),
            "frequency_range": [min(frequencies), max(frequencies)],
            "qpoints": len(qpoints),
            "branches": len(branches),
            "structure": dos.get("structure"),
            "scope": "published DFPT band structure and DOS; no new phonon calculation",
        }
    )


THERMO_FIELDS = {
    "electronic_energy",
    "zero_point_energy",
    "total_enthalpy",
    "total_entropy",
    "translational_enthalpy",
    "translational_entropy",
    "rotational_enthalpy",
    "rotational_entropy",
    "vibrational_enthalpy",
    "vibrational_entropy",
    "free_energy",
}
VIBRATION_FIELDS = {"frequencies", "frequency_modes", "ir_intensities", "ir_activities"}
ORBITAL_FIELDS = {"open_shell", "nbo_population"}

def molecule_property(molecule_id, property_name):
    """Read the exact requested field; never substitute unique/total for a missing scalar/component.

    Public collection primitives use unique_* explicitly. Legacy singular
    registrations are retired, rather than disguising a collection as a scalar.
    """
    group = None
    nested_name = property_name
    if property_name in THERMO_FIELDS:
        group = "thermo"
    elif property_name in VIBRATION_FIELDS:
        group = "vibration"
    elif property_name in ORBITAL_FIELDS:
        group = "orbitals"
    else:
        for candidate in ["thermo", "vibration", "orbitals"]:
            if property_name == candidate + "_property_ids":
                group, nested_name = candidate, "property_id"
            elif property_name == candidate + "_levels_of_theory":
                group, nested_name = candidate, "level_of_theory"
    field = group or property_name
    requested_fields = (
        field + ",deprecated" if property_name == "deprecation_reasons" else field
    )
    record = get(
        "https://api.materialsproject.org/molecules/summary/",
        params={
            "molecule_ids": molecule_id,
            "_fields": requested_fields,
            "_all_fields": "false",
            "_limit": 1,
        },
    ).json()["data"][0]
    if not group:
        if (
            property_name == "deprecation_reasons"
            and record.get("deprecated") is False
            and record.get(field) is None
        ):
            return []
        if field not in record or record[field] is None:
            raise MissingScientificData(
                f"{field} is unavailable for molecule {molecule_id}"
            )
        return record[field]
    section = record.get(group)
    if not isinstance(section, dict) or not section:
        raise MissingScientificData(
            f"{group} is unavailable for molecule {molecule_id}"
        )
    values = {
        solvent: item[nested_name]
        for solvent, item in section.items()
        if isinstance(item, dict) and item.get(nested_name) is not None
    }
    if not values:
        raise MissingScientificData(
            f"{property_name} is not published for molecule {molecule_id}"
        )
    return values


def eos_for_material(material_id):
    """Resolve the material's actual task IDs before requesting EOS; no unrelated task substitution."""
    material_id = material_id.strip(" \"'")
    core = get(
        "https://api.materialsproject.org/materials/core/",
        params={
            "material_ids": material_id,
            "_fields": "material_id,task_ids",
            "_limit": 1,
        },
    ).json()["data"][0]
    task_ids = core.get("task_ids")
    if not task_ids:
        raise MissingScientificData("The material has no published task IDs")
    payload = get(
        "https://api.materialsproject.org/materials/eos/",
        params={
            "task_ids": ",".join(task_ids),
            "_all_fields": "true",
            "_limit": 100,
        },
    ).json()
    records = payload["data"]
    if any(str(record.get("task_id")) not in task_ids for record in records):
        raise RuntimeError("EOS result is not associated with this material's tasks")
    return json.dumps(
        {
            "source": "Materials Project materials/core -> materials/eos",
            "input_material_id": material_id,
            "resolved_material_id": core["material_id"],
            "energy_units": "eV",
            "volume_units": "angstrom^3",
            "documents": records,
        }
    )
