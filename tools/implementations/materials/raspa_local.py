"""Real RASPA2 adsorption simulation with explicit conditions and retained raw artifacts."""

from scitoolflow.paths import local_root, artifacts_root
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

ROOT = local_root()


def predict_adsorption(
    cif_file_name: str,
    temperature: float = 298.0,
    pressure: float = 100000.0,
    production_cycles: int = 2000,
    initialization_cycles: int = 100,
    co2_mole_fraction: float = 0.5,
):
    """RASPA2 CO2/H2 mixture adsorption, mg/g; short-run call validation does not certify equilibrium convergence."""
    from pymatgen.core import Structure
    from tools.runtime.config import Config

    config = Config()
    filename = (
        cif_file_name if cif_file_name.endswith(".cif") else cif_file_name + ".cif"
    )
    cif = Path(config.UPLOAD_FILES_BASE_PATH) / filename
    if not cif.is_file():
        raise FileNotFoundError(str(cif))
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
        import hashlib

        source = definitions / item["name"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError(
                "Forcefield definition content differs from verified generation manifest"
            )
        shutil.copyfile(source, directory / source.name)
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
    return json.dumps(
        {
            "source": "iRASPA/RASPA2 local simulation",
            "input_cif": str(cif),
            "finished": True,
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
            "warnings": sorted(set(re.findall(r"WARNING: (.*)", raw))),
            "raw_output": str(outputs[0]),
        }
    )
