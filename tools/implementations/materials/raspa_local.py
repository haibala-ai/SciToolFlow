"""Real RASPA2 adsorption simulation with explicit conditions and retained raw artifacts."""

from src.utils.paths import local_root, artifacts_root
import json
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

ROOT = local_root()


def _inventory_mass_basis(raw, definitions, unit_cells, source_cell_volume):
    """Decode actual printed inventory units and verify their common model basis.

    Framework Mass/Volume are for the simulation supercell; reported molecular
    counts are already per original crystallographic unit cell. Definition
    masses are validated against the simulator's actual molecule report.
    """
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    def repeated(pattern, label, positive=True):
        found = [float(v) for v in re.findall(pattern, raw, re.MULTILINE)]
        if not found or not all(math.isfinite(v) and (not positive or v > 0) for v in found):
            raise RuntimeError("Missing or invalid RASPA " + label)
        if any(not math.isclose(v, found[0], rel_tol=1e-9, abs_tol=1e-8) for v in found[1:]):
            raise RuntimeError("Contradictory RASPA " + label)
        return found[0]
    mass = repeated(r"^Framework Mass:\s*(" + number + r")\s*\[g/mol\]", "framework mass")
    density = repeated(r"^Framework Density:\s*(" + number + r")\s*\[kg/m\^3\]", "framework density")
    simulation_volume = repeated(r"^Volume:\s*(" + number + r")\s*\[A\^3\]", "simulation volume")
    replication = math.prod(unit_cells)
    for axis, count in zip("abc", unit_cells):
        actual = re.findall(r"^Number of unitcells \[" + axis + r"\]:\s*(\d+)\s*$", raw, re.MULTILINE)
        if actual != [str(count)]:
            raise RuntimeError("RASPA unit-cell replication does not match requested simulation")
    unit_volume = simulation_volume / replication
    if not math.isclose(unit_volume, source_cell_volume, rel_tol=1e-7, abs_tol=1e-5):
        raise RuntimeError("RASPA simulation volume differs from uploaded CIF cell")
    # Density uses the simulator's physical constants. This consistency bound
    # allows its documented older Avogadro constant; do not replace raw values.
    reference_density = mass / simulation_volume * (1e27 / 6.02214076e23)
    if not math.isclose(density, reference_density, rel_tol=2e-6):
        raise RuntimeError("RASPA framework mass, volume and density contradict one another")
    pseudo = {}
    for line in (definitions / "pseudo_atoms.def").read_text().splitlines():
        columns = line.split()
        if len(columns) >= 6 and columns[1] in {"True", "False", "yes", "no"}:
            name, value = columns[0], float(columns[5])
            if name in pseudo or not math.isfinite(value) or value <= 0:
                raise RuntimeError("Invalid or duplicate molecule pseudo-atom mass definition")
            pseudo[name] = value
    model_masses = {}
    for index, gas in enumerate(["CO2", "H2"]):
        definition = (definitions / (gas + ".def")).read_text()
        positions = re.search(r"# Group-1: Atomic positions\s*\n(.*?)\n# Chiral centers", definition, re.DOTALL)
        if not positions:
            raise RuntimeError("Unsupported molecular mass definition layout")
        types = []
        for line in positions.group(1).splitlines():
            fields = line.split()
            if len(fields) != 5 or not fields[0].isdigit() or fields[1] not in pseudo:
                raise RuntimeError("Unsupported or missing molecule pseudo-atom definition")
            types.append(fields[1])
        calculated = sum(pseudo[name] for name in types)
        component = re.search(r"^Component " + str(index) + r" \[" + gas + r"\] \(Adsorbate molecule\)(.*?)(?=^Component \d+ \[[^\n]+\] \(Adsorbate molecule\)|\Z)", raw, re.MULTILINE | re.DOTALL)
        reported = re.findall(r"^\s*Mass:\s*(" + number + r")\s*\[a\.u\.\]", component.group(1) if component else "", re.MULTILINE)
        if len(reported) != 1 or not math.isclose(float(reported[0]), calculated, rel_tol=1e-9, abs_tol=1e-6):
            raise RuntimeError("RASPA component mass differs from verified molecule definitions")
        model_masses[gas] = calculated
    inventories = {}
    for kind in ["absolute", "excess"]:
        found = re.findall(r"Average loading " + kind + r" \[molecules/unit cell\]\s*(" + number + r")\s*\+/-\s*(" + number + r")", raw)
        if len(found) != 2:
            raise RuntimeError("Missing or multiple two-component molecular inventory reports")
        inventories[kind] = {}
        for gas, (mean, width) in zip(["CO2", "H2"], found):
            values = [float(mean), float(width)]
            if not all(math.isfinite(v) for v in values) or values[1] < 0 or (kind == "absolute" and values[0] < 0):
                raise RuntimeError("Invalid molecular inventory or block uncertainty")
            inventories[kind][gas] = {"mean": values[0], "confidence_interval_95": values[1]}
    return {
        "molecular_inventory_units": "molecules per crystallographic unit cell",
        "molecular_inventory": inventories,
        "model_molar_masses_g_per_mol": model_masses,
        "framework_mass_basis": {
            "normalization": "RASPA pseudo-atom model masses; not ordinary average atomic weights",
            "simulation_supercell_mass_g_per_mol": mass,
            "crystallographic_cell_mass_g_per_mol": mass / replication,
            "density_kg_per_m3": density,
            "simulation_supercell_volume_angstrom_cubed": simulation_volume,
            "crystallographic_cell_volume_angstrom_cubed": unit_volume,
            "unit_cell_replication": list(unit_cells),
        },
    }


def predict_adsorption(
    cif_file_name: str,
    temperature: float = 298.0,
    pressure: float = 100000.0,
    production_cycles: int = 2000,
    initialization_cycles: int = 100,
    co2_mole_fraction: float = 0.5,
):
    """RASPA2 CO2/H2 mixture adsorption, mg/g; short-run call validation does not certify equilibrium convergence.

    Returns a JSON string with actual input CIF source_sha256, explicit
    conditions, absolute/excess gas loadings and retained raw output. Additional
    per-crystallographic-cell molecular inventories and actual model mass/volume
    basis expose the simulation normalization without changing legacy mg/g.
    Molecular model masses are read from verified definitions and checked against
    actual raw reports; incompatible or missing unit records fail explicitly. A source
    changed during the simulation raises an explicit error. Forcefield,
    random seed and sampling algorithms are not altered by provenance output.
    """
    from pymatgen.core import Structure
    from tools.runtime.config import Config

    if not isinstance(cif_file_name, str) or not cif_file_name.strip():
        raise ValueError("cif_file_name must be an explicit CIF attachment name/path")
    for name, value in [("temperature", temperature), ("pressure", pressure),
                        ("co2_mole_fraction", co2_mole_fraction)]:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(name + " must be a finite number, not a boolean")
    if type(production_cycles) is not int or type(initialization_cycles) is not int:
        raise ValueError("Cycle counts must be integers, not booleans or fractional values")
    config = Config()
    filename = (
        cif_file_name if cif_file_name.endswith(".cif") else cif_file_name + ".cif"
    )
    cif = Path(config.UPLOAD_FILES_BASE_PATH) / filename
    if not cif.is_file():
        raise FileNotFoundError(str(cif))
    source_sha256 = hashlib.sha256(cif.read_bytes()).hexdigest()
    if "_atom_site_charge" not in cif.read_text():
        raise ValueError(
            "Adsorption simulation requires explicit CIF atom charges; none are invented"
        )
    if not 0 < co2_mole_fraction < 1 or temperature < 273 or pressure <= 0:
        raise ValueError(
            "Buch-nonFH H2 requires temperature >=273 K; require positive pressure and 0<CO2 fraction<1"
        )
    if not 1 <= production_cycles <= 100000 or not 0 <= initialization_cycles <= 100000:
        raise ValueError("Cycle counts exceed the bounded local simulation contract")
    structure = Structure.from_file(cif)
    import numpy as np

    cell = structure.lattice.matrix
    volume = structure.volume
    heights = [
        volume / np.linalg.norm(np.cross(cell[(i + 1) % 3], cell[(i + 2) % 3]))
        for i in range(3)
    ]
    cutoff = 12.0
    cells = [math.floor(2 * cutoff / height) + 1 for height in heights]
    if len(structure) * math.prod(cells) > 20000:
        raise ValueError("Simulation supercell exceeds 20000 framework atoms")
    directory = artifacts_root() / ("raspa_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    shutil.copyfile(cif, directory / "framework.cif")
    definitions = ROOT / "external_sources/raspa_forcefields"
    manifest = json.loads((definitions / "manifest.json").read_text())
    for item in manifest["files"]:
        source = definitions / item["name"]
        definition_bytes = source.read_bytes()
        if hashlib.sha256(definition_bytes).hexdigest() != item["sha256"]:
            raise RuntimeError(
                "Forcefield definition content differs from verified generation manifest"
            )
        (directory / source.name).write_bytes(definition_bytes)
    forcefield = "local"
    molecular_definition = "local"
    text = f"""SimulationType MonteCarlo
NumberOfCycles {production_cycles}
NumberOfInitializationCycles {initialization_cycles}
PrintEvery 100
RestartFile no
RandomSeed 42
Forcefield {forcefield}
UseChargesFromCIFFile yes
ChargeMethod Ewald
Framework 0
FrameworkName framework
CutOffVDW {cutoff}
UnitCells {' '.join(map(str, cells))}
ExternalTemperature {temperature}
ExternalPressure {pressure}
Component 0 MoleculeName CO2
            MoleculeDefinition {molecular_definition}
            MolFraction {co2_mole_fraction}
            TranslationProbability 0.5
            RotationProbability 0.5
            ReinsertionProbability 0.5
            SwapProbability 1.0
            CreateNumberOfMolecules 0
Component 1 MoleculeName H2
            MoleculeDefinition {molecular_definition}
            MolFraction {1-co2_mole_fraction}
            TranslationProbability 0.5
            RotationProbability 0.5
            ReinsertionProbability 0.5
            SwapProbability 1.0
            CreateNumberOfMolecules 0
"""
    (directory / "simulation.input").write_text(text)
    executable = Path(config.RASPA_EXECUTABLE_PATH)
    executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    runtime = executable.parent.parent
    env = os.environ.copy()
    env["RASPA_DIR"] = str(runtime)
    env["LD_LIBRARY_PATH"] = str(runtime / "lib") + ":" + env.get("LD_LIBRARY_PATH", "")
    with (directory / "simulation.log").open("w") as log:
        completed = subprocess.run(
            [str(executable), "simulation.input"],
            cwd=directory,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=900,
        )
    outputs = sorted(directory.glob("Output/System_0/*.data"))
    if completed.returncode or len(outputs) != 1:
        raise RuntimeError(
            "RASPA failed or produced no unique output; log: "
            + str(directory / "simulation.log")
        )
    if hashlib.sha256(executable.read_bytes()).hexdigest() != executable_sha256:
        raise RuntimeError("RASPA executable changed during simulation")
    raw = outputs[0].read_text()
    if "Simulation finished" not in raw:
        raise RuntimeError(
            "RASPA output does not certify simulation completion: " + str(outputs[0])
        )
    value_pattern = r"([-+\d.eE]+)\s*\+/-\s*([-+\d.eE]+)"
    adsorption = {}
    for kind in ["absolute", "excess"]:
        matches = re.findall(
            r"Average loading "
            + kind
            + r" \[milligram/gram framework\]\s*"
            + value_pattern,
            raw,
        )
        if len(matches) != 2:
            raise RuntimeError(
                "Unexpected two-component RASPA adsorption output schema"
            )
        adsorption[kind] = {
            gas: {"mean": float(mean), "confidence_interval_95": float(error)}
            for gas, (mean, error) in zip(["CO2", "H2"], matches)
        }
    if not all(
        math.isfinite(item[key])
        for group in adsorption.values()
        for item in group.values()
        for key in item
    ):
        raise RuntimeError("Non-finite RASPA adsorption output")
    inventory_basis = _inventory_mass_basis(raw, directory, cells, float(volume))
    cell_mass = inventory_basis["framework_mass_basis"]["crystallographic_cell_mass_g_per_mol"]
    for kind, groups in inventory_basis["molecular_inventory"].items():
        for gas, quantities in groups.items():
            factor = inventory_basis["model_molar_masses_g_per_mol"][gas] * 1000.0 / cell_mass
            for key in ["mean", "confidence_interval_95"]:
                if not math.isclose(quantities[key] * factor, adsorption[kind][gas][key], rel_tol=2e-7, abs_tol=1e-7):
                    raise RuntimeError("Molecular inventory and mass-normalized adsorption contradict one another")
    if hashlib.sha256(cif.read_bytes()).hexdigest() != source_sha256:
        raise RuntimeError("Input CIF changed during the adsorption calculation")
    return json.dumps(
        {
            "source": "iRASPA/RASPA2 local simulation",
            "input_cif": str(cif),
            "source_sha256": source_sha256,
            "finished": True,
            "simulation_binary_sha256": executable_sha256,
            "random_seed": 42,
            "temperature_kelvin": temperature,
            "pressure_pascal": pressure,
            "mixture_mole_fractions": {
                "CO2": co2_mole_fraction,
                "H2": 1 - co2_mole_fraction,
            },
            "production_cycles": production_cycles,
            "initialization_cycles": initialization_cycles,
            "equilibrium_convergence_verified": False,
            "forcefield": forcefield,
            "forcefield_parameters": manifest["parameters"],
            "forcefield_provenance": manifest["source"],
            "molecule_definition": molecular_definition,
            "cutoff_angstrom": cutoff,
            "unit_cells": cells,
            "adsorption_units": "mg/g framework",
            "adsorption": adsorption,
            **inventory_basis,
            "warnings": sorted(set(re.findall(r"WARNING: (.*)", raw))),
            "raw_output": str(outputs[0]),
        }
    )
