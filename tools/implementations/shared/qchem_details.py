"""Read real molecular detail fields from an explicitly supplied Q-Chem output.

This adapter never assigns a fixture to an unrelated MP molecule identifier and
does not run a quantum-chemistry engine or manufacture missing properties.
"""

from scitoolflow.paths import local_root, artifacts_root
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

from tools.implementations.shared.materials_api import MissingScientificData

ROOT = local_root()
FIELDS = {
    "translational_enthalpy": ("trans_enthalpy", "kcal/mol"),
    "rotational_enthalpy": ("rot_enthalpy", "kcal/mol"),
    "vibrational_enthalpy": ("vib_enthalpy", "kcal/mol"),
    "translational_entropy": ("trans_entropy", "cal/(mol K)"),
    "rotational_entropy": ("rot_entropy", "cal/(mol K)"),
    "vibrational_entropy": ("vib_entropy", "cal/(mol K)"),
    "frequency_modes": (
        "frequency_mode_vectors",
        "Q-Chem displacement-vector normalization",
    ),
    "ir_intensities": ("IR_intens", "km/mol"),
    "ir_activities": ("IR_active", "boolean"),
    "nbo_population": ("nbo_data", "electrons; original NPA columns retained"),
}


def plain(value):
    if hasattr(value, "tolist"):
        return plain(value.tolist())
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise MissingScientificData(
            "Requested Q-Chem result contains non-finite values"
        )
    return value


@lru_cache(maxsize=8)
def parse_output(path_text, source_sha256):
    from pymatgen.io.qchem.outputs import QCOutput

    output = QCOutput(path_text)
    if not output.data.get("completion") or output.data.get("errors"):
        raise MissingScientificData(
            "Q-Chem output is incomplete or contains calculation errors"
        )
    return output.data


def extract_property(identifier, property_name):
    if property_name not in FIELDS:
        raise ValueError("Unsupported Q-Chem detail property")
    if not identifier.startswith("qchem:"):
        raise ValueError("Expected qchem:/path/to/completed_output.qout[.gz]")
    path = Path(identifier[6:]).expanduser()
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not path.is_file():
        raise MissingScientificData("Supplied Q-Chem output file does not exist")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Q-Chem output exceeds the 20 MiB input limit")
    raw = path.read_bytes()
    if raw.startswith(b"\x1f\x8b"):
        with gzip.open(path, "rb") as stream:
            decoded = stream.read(100 * 1024 * 1024 + 1)
        if len(decoded) > 100 * 1024 * 1024:
            raise ValueError("Decoded Q-Chem output exceeds the 100 MiB limit")
    else:
        decoded = raw
    digest = hashlib.sha256(raw).hexdigest()
    data = parse_output(str(path), digest)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Q-Chem output changed while being parsed")
    field, units = FIELDS[property_name]
    value = data.get(field)
    if property_name == "nbo_population":
        tables = value.get("natural_populations") if isinstance(value, dict) else None
        if not tables:
            raise MissingScientificData(
                "Supplied Q-Chem output has no real NBO natural populations"
            )
        value = {"natural_population_tables": tables}
    if value is None or (hasattr(value, "__len__") and len(value) == 0):
        raise MissingScientificData(
            f"Supplied Q-Chem output does not contain {property_name}"
        )
    value = plain(value)
    if property_name == "ir_activities":
        if any(flag not in {"YES", "NO"} for flag in value):
            raise MissingScientificData("Unexpected Q-Chem IR activity flag")
        value = [flag == "YES" for flag in value]
    molecule = data.get("initial_molecule")
    temperature = re.search(
        r"Temperature\s*(?:=|:)\s*([\d.]+)\s*K", decoded.decode("latin-1"), re.I
    )
    if temperature is None:
        temperature = re.search(
            r"STANDARD\s+THERMODYNAMIC\s+QUANTITIES\s+AT\s+([\d.]+)\s*K",
            decoded.decode("latin-1"),
            re.I,
        )
    result = {
        "backend": "supplied_qchem_output",
        "property": property_name,
        "source_file": str(path),
        "source_sha256": digest,
        "formula": molecule.composition.formula if molecule is not None else None,
        "temperature_k": float(temperature.group(1)) if temperature else None,
        "units": units,
        "value": value,
        "scope": "Values parsed from this completed calculation only; not a Materials Project lookup or a new calculation",
        "mp_molecule_identity_verified": False,
    }
    return json.dumps(result, ensure_ascii=False, allow_nan=False)
