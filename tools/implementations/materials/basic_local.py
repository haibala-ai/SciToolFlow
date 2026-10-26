"""New implementations for basic KG nodes, with narrow, explicit scientific contracts."""

import json
import hashlib
import math
from pathlib import Path
import re


def _file(name):
    from tools.runtime.config import Config

    path = Path(name)
    if not path.is_absolute():
        path = Path(Config().UPLOAD_FILES_BASE_PATH) / path
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def convert_units(query: str):
    """Pint unit conversion, input '25 degree_Celsius to kelvin'; supports numeric physical units, not currency."""
    from pint import UnitRegistry

    if not isinstance(query, str) or len(query) > 512:
        raise ValueError("query must be text of at most512characters")
    match = re.fullmatch(
        r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+(.+?)\s+to\s+(.+?)\s*",
        query,
    )
    if not match:
        raise ValueError("Use '<number> <source unit> to <target unit>'")
    value, source, target = match.groups()
    units = UnitRegistry()
    converted = units.Quantity(float(value), source).to(target)
    if not math.isfinite(float(value)) or not math.isfinite(float(converted.magnitude)):
        raise ValueError("Input and converted values must be finite")
    return json.dumps(
        {
            "implementation": "Pint",
            "input_value": float(value),
            "input_unit": source,
            "converted_value": float(converted.magnitude),
            "converted_unit": str(converted.units),
        }
    )


def search_csv(csv_file: str, column: str, value: str, max_results: int = 20):
    """Find exact text matches in one named CSV column; does not infer missing MOF properties."""
    import pandas as pd

    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be in [1,100]")
    path = _file(csv_file)
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("CSV files are limited to 100 MiB")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if column not in frame.columns:
        raise ValueError("Unknown column: " + column)
    selected = frame.loc[frame[column] == str(value)]
    return json.dumps(
        {
            "source_csv": str(path),
            "filter": {"column": column, "exact_value": value},
            "total_matches": len(selected),
            "returned_rows": selected.head(max_results).to_dict("records"),
            "truncated": len(selected) > max_results,
        }
    )


def ase_properties(structure_file: str):
    """ASE static structure properties with source byte hash; no simulated energies.

    Returns the existing JSON-string format, including source_file and
    source_sha256 for portable provenance, formula, cell and coordinates.
    """
    from ase.io import read

    source = _file(structure_file)
    atoms = read(str(source))
    if not len(atoms):
        raise ValueError("Structure contains no atoms")
    for site in atoms.info.get("occupancy", {}).values():
        if len(site) != 1 or any(
            abs(float(occupation) - 1) > 1e-6 for occupation in site.values()
        ):
            raise ValueError(
                "Static property adapter does not support partial/disordered site occupancy"
            )
    volume = float(atoms.get_volume()) if atoms.cell.rank == 3 else None
    mass = float(atoms.get_masses().sum())
    return json.dumps(
        {
            "implementation": "ASE",
            "source_file": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "atoms": len(atoms),
            "formula": atoms.get_chemical_formula(),
            "mass_u": mass,
            "volume_angstrom_cubed": volume,
            "density_g_per_cm3": (
                1.66053906660 * mass / volume if volume and atoms.pbc.all() else None
            ),
            "cell_angstrom": atoms.cell.tolist(),
            "periodic_boundary_conditions": atoms.pbc.tolist(),
            "atomic_numbers": atoms.numbers.tolist(),
            "positions_angstrom": atoms.positions.tolist(),
        }
    )


def calculate_density(file_name: str) -> dict:
    """Calculate static periodic-cell mass density with complete source provenance.

    Args:
        file_name: Existing periodic structure file supported by pymatgen,
            such as CIF or POSCAR; absolute path or task attachment name.
            The supplied cell must have finite positive volume and mass.

    Returns:
        density_g_per_cm3, mass_u and volume_angstrom_cubed as unrounded finite
        numbers; sites, formula, source_file, source_sha256 and method. Density
        uses occupancy-weighted cell mass and the supplied cell volume. It is
        not a measured bulk/powder density, porosity estimate or relaxed state.

    Raises:
        FileNotFoundError: Missing source file.
        ValueError: Unreadable structure, nonpositive/nonfinite volume or mass,
            or a source file that changes while it is being read. No error is
            returned as a successful density observation.
    """
    from pymatgen.core import Structure

    path = _file(file_name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        structure = Structure.from_file(path)
        volume = float(structure.volume)
        mass = float(structure.composition.weight)
        density = float(structure.density)
    except Exception as exc:
        raise ValueError("Cannot calculate periodic-cell density: " + str(exc)) from exc
    if not all(math.isfinite(v) and v > 0 for v in [volume, mass, density]):
        raise ValueError("Cell volume, occupancy-weighted mass and density must be finite and positive")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Source structure changed while density was being calculated")
    return {
        "density_g_per_cm3": density,
        "mass_u": mass,
        "volume_angstrom_cubed": volume,
        "sites": len(structure),
        "formula": structure.composition.formula,
        "source_file": path.name,
        "source_sha256": digest,
        "method": "pymatgen static periodic-cell density; occupancy-weighted cell mass / cell volume",
    }


def structure_to_smiles(structure_file: str):
    """OpenBabel conversion for mol2/mol/sdf/pdbqt/pdb; coordinate-only inputs require bond/charge perception."""
    from openbabel import pybel

    path = _file(structure_file)
    format = path.suffix.lstrip(".").lower()
    if format not in ["mol2", "mol", "sdf", "pdbqt", "pdb"]:
        raise ValueError("Supported structural formats: mol2, mol, sdf, pdbqt, pdb")
    results = []
    for molecule in pybel.readfile(format, str(path)):
        if not molecule.atoms:
            raise ValueError("Structural molecule contains no atoms")
        results.append(
            {
                "title": molecule.title,
                "smiles": molecule.write("can").strip().split()[0],
            }
        )
    if not results:
        raise ValueError("No structural molecules were read")
    return json.dumps(
        {
            "implementation": "OpenBabel",
            "source_file": str(path),
            "format": format,
            "molecules": results,
            "coordinate_only_input_note": "Bond orders and charges may require OpenBabel perception; provide explicit chemistry where available.",
        }
    )
