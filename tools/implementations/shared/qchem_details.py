"""Read real molecular detail fields from an explicitly supplied Q-Chem output.

This adapter never assigns a fixture to an unrelated MP molecule identifier and
does not run a quantum-chemistry engine or manufacture missing properties.
"""

from src.utils.paths import local_root, artifacts_root
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
    "frequencies": ("frequencies", "cm^-1"),
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


def normalize_ir_activity_flags(value, text, frequency_count):
    """Align printed flags while allowing only verified trailing parser padding.

    Some pymatgen versions append two ``"None"`` strings for a final
    single-mode block. The original Mode/IR Active columns must establish the
    same complete frequency count before those placeholders can be removed.
    A printed YES is preserved even when the printed intensity is zero; this
    field is the output flag, not an independent symmetry-selection proof.
    """
    if type(frequency_count) is not int or frequency_count <= 0:
        raise MissingScientificData("IR activities require a positive frequency count")
    modes = re.findall(r"(?m)^[ \t]*Mode:[ \t]*([0-9 \t]+)[ \t]*\r?$", text)
    columns = re.findall(r"(?mi)^[ \t]*IR[ \t]+Active:[ \t]*(.*?)\r?$", text)
    if not modes or len(modes) != len(columns):
        raise MissingScientificData("Q-Chem Mode/IR Active blocks are missing or misaligned")
    printed, mode_numbers = [], []
    for labels, flags in zip(modes, columns):
        labels, flags = labels.split(), flags.split()
        if len(labels) != len(flags) or any(int(i) <= 0 for i in labels):
            raise MissingScientificData("Q-Chem Mode/IR Active column counts disagree")
        if any(flag not in {"YES", "NO"} for flag in flags):
            raise MissingScientificData("Unexpected printed Q-Chem IR activity flag")
        mode_numbers.extend(int(i) for i in labels)
        printed.extend(flags)
    if len(printed) != frequency_count:
        raise MissingScientificData("Q-Chem IR activity and actual frequency counts disagree")
    if mode_numbers != list(range(1, frequency_count + 1)):
        raise MissingScientificData("Q-Chem printed modes are not a complete ordered frequency sequence")
    if not isinstance(value, list) or len(value) < frequency_count:
        raise MissingScientificData("Parsed Q-Chem IR activity list is incomplete")
    if value[:frequency_count] != printed:
        raise MissingScientificData("Parsed IR flags disagree with the original printed columns")
    if any(flag is not None and flag != "None" for flag in value[frequency_count:]):
        raise MissingScientificData("Unexpected extra parsed Q-Chem IR activity values")
    return [flag == "YES" for flag in printed]


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
        # Preserve the raw population-table identity. Summed/alpha/beta tables
        # must not be added together as independent observations. Labels come
        # from printed headings,never from guesses based on electron totals.
        text = decoded.decode("latin-1")
        summaries = list(re.finditer(r"Summary of Natural Population Analysis:", text))
        channels = list(re.finditer(r"(?im)^.*?\b(alpha|beta)\s+spin\s+orbitals.*$", text))
        contexts = []
        aligned = len(summaries) == len(tables)
        for index, table in enumerate(tables):
            channel, evidence, heading = "unknown", "unmatched source table headings", None
            if aligned:
                start = summaries[index].end()
                fragment = text[start : start + 350]
                # NBO's spin-summed open-shell table explicitly prints a
                # Natural Spin Density column; individual spin tables do not.
                if re.search(r"(?m)^.*\bNatural[ \t]*\r?\n.*\bSpin[ \t]*\r?\n.*\bDensity[ \t]*$", fragment):
                    channel = "combined"
                    evidence = "printed Natural Spin Density column in this table header"
                    heading = "Natural Spin Density"
                else:
                    prior = [marker for marker in channels if marker.start() < summaries[index].start()]
                    if prior:
                        channel = prior[-1].group(1).lower()
                        evidence = "most recent printed spin-channel heading preceding this table"
                        heading = prior[-1].group(0).strip()
                    else:
                        evidence = "no explicit source spin-channel heading; no label inferred"
            contexts.append({"table_index": index, "spin_channel": channel,
                             "source_heading": heading, "context_evidence": evidence})
        value = {"natural_population_tables": tables,
                 "table_context": contexts, "table_context_aligned_to_source": aligned}
    if value is None or (hasattr(value, "__len__") and len(value) == 0):
        raise MissingScientificData(
            f"Supplied Q-Chem output does not contain {property_name}"
        )
    value = plain(value)
    if property_name == "ir_activities":
        frequencies = data.get("frequencies")
        count = len(frequencies) if frequencies is not None else 0
        value = normalize_ir_activity_flags(value, decoded.decode("latin-1"), count)
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
        "molecular_charge": plain(data.get("charge")),
        "spin_multiplicity": plain(data.get("multiplicity")),
        "units": units,
        "value": value,
        "scope": "Values parsed from this completed calculation only; not a Materials Project lookup or a new calculation",
        "mp_molecule_identity_verified": False,
    }
    return json.dumps(result, ensure_ascii=False, allow_nan=False)
