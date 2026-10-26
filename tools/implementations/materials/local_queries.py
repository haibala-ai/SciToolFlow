"""Local structure and MOF primitives with exact source identity and explicit failures."""

import hashlib
import json
import math
from pathlib import Path

from tools.implementations.materials.basic_local import _file


def _finite_json(value):
    """Preserve scientific values while converting tuple/NumPy containers to JSON.

    Pymatgen's Structure.as_dict is an MSON dictionary, not necessarily a plain
    JSON object: lattice pbc can be a tuple and site properties can use NumPy.
    Unsupported objects and nonfinite numbers fail instead of becoming text.
    """
    import numpy as np

    if isinstance(value, np.ndarray):
        return _finite_json(value.tolist())
    if isinstance(value, np.generic):
        native = value.item()
        if isinstance(native, np.generic):
            raise TypeError("NumPy scalar has no lossless native JSON representation: " + str(value.dtype))
        return _finite_json(native)
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Scientific structure output contains a nonfinite number")
        return value
    if isinstance(value, (list, tuple)):
        return [_finite_json(item) for item in value]
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: _finite_json(item) for key, item in value.items()}
    raise TypeError("Scientific structure output is not expressible as JSON: " + type(value).__name__)


def _source(file_name):
    if not isinstance(file_name, str) or not file_name.strip() or len(file_name) > 4096:
        raise ValueError("Supply one explicit existing structure file path or attachment name")
    path = _file(file_name)
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Structure sources are limited to10MiB")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _unchanged(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Source structure bytes changed during parsing/analysis")


def _structure(file_name):
    from pymatgen.core import Structure

    path, digest = _source(file_name)
    structure = (Structure.from_file(path, frac_tolerance=0)
        if path.name.lower().endswith((".cif", ".mcif", ".cif.gz", ".mcif.gz"))
        else Structure.from_file(path))
    if not 1 <= len(structure) <= 10000 or not math.isfinite(structure.volume) or structure.volume <= 0:
        raise ValueError("Structure requires1..10000sites and finite positive cell volume")
    _finite_json(structure.as_dict())
    _unchanged(path, digest)
    return structure, path, digest


def read_crystal_structure(structure_file: str) -> dict:
    """Parse one periodic crystal file into complete geometry, preserving the supplied cell and occupancies.

    Returns the original parsed pymatgen Structure (cell/site coordinates/species/
    occupancies), parser version and exact source byte hash. No primitive-cell
    reduction, chemical-bond assignment, density or electronic property is inferred.
    Explicit CIF fractional coordinates are preserved with frac_tolerance=0.
    """
    from importlib.metadata import version

    structure, path, digest = _structure(structure_file)
    return _finite_json({"source_file": str(path), "source_sha256": digest,
            "structure": structure.as_dict(), "length_units": "angstrom",
            "cell_role": "Parsed input cell, without primitive reduction",
            "parser": "pymatgen", "parser_version": version("pymatgen")})


def get_catalogue_price(cas: str) -> dict:
    """Retrieve public supplier mass-package quotes and their unweighted CNY/g mean for one checksum-valid CAS number. No market-wide/member price is inferred."""
    from tools.implementations.shared.catalogue_price import public_catalogue_price

    return json.loads(public_catalogue_price(cas))


def get_element_composition(file_name: str) -> dict:
    """Return occupancy-weighted elemental amounts in the parsed supplied crystal cell, not reduced-formula amounts or phase purity."""
    structure, path, digest = _structure(file_name)
    return _finite_json({"source_file": str(path), "source_sha256": digest,
            "element_amounts": structure.composition.get_el_amt_dict(),
            "basis": "Occupancy-weighted atoms per parsed input cell"})


def calculate_symmetry(file_name: str, symprec: float = 0.01,
                        angle_tolerance: float = 5.0) -> dict:
    """Infer nonmagnetic crystallographic space group for supplied geometry with explicit tolerances.

    symprec is a Cartesian distance tolerance in angstrom (0,1]; angle_tolerance
    is degrees (0,15]. Returns symbol/international number/source hash and actual
    settings. This is not stored MP symmetry or magnetic space-group inference.
    """
    for name, value, bound in [("symprec", symprec, 1), ("angle_tolerance", angle_tolerance, 15)]:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= bound:
            raise ValueError(name + " must be a finite positive number within the documented bound")
    structure, path, digest = _structure(file_name)
    if not structure.is_ordered:
        raise ValueError("Space-group inference supports ordered/full-occupancy structures only")
    symbol, number = structure.get_space_group_info(symprec=symprec, angle_tolerance=angle_tolerance)
    _unchanged(path, digest)
    return {"source_file": str(path), "source_sha256": digest,
            "space_group_symbol": symbol, "international_number": int(number),
            "symprec_angstrom": symprec, "angle_tolerance_degrees": angle_tolerance,
            "method": "pymatgen/spglib nonmagnetic geometry analysis"}


def _mof(cif_file_name, graph_required=True):
    if isinstance(cif_file_name, str) and not Path(cif_file_name).suffix:
        cif_file_name += ".cif"
    path, digest = _source(cif_file_name)
    if path.suffix.lower() != ".cif":
        raise ValueError("MOF graph analysis requires an explicit .cif filename")
    if graph_required:
        from moffragmentor.mof import MOF
        mof = MOF.from_cif(str(path))
    else:
        # Exactly the installed MOF.from_cif default geometry sequence, without
        # constructing an unused VESTA bond graph for lattice/site queries.
        from pymatgen.core import IStructure
        from types import SimpleNamespace
        structure = IStructure.from_file(path).get_primitive_structure(0.5)
        structure = IStructure.from_sites(structure)
        mof = SimpleNamespace(structure=structure, lattice=structure.lattice,
                              frac_coords=structure.frac_coords)
    if not 1 <= len(mof.structure) <= 2000:
        raise ValueError("MOF graph analysis supports1..2000sites in its default cell")
    _unchanged(path, digest)
    return mof, path, digest


def _mof_result(mof, path, digest, **fields):
    from importlib.metadata import version

    _unchanged(path, digest)
    result = {"source_file": str(path), "source_sha256": digest,
              "cell_role": "moffragmentor default MOF.from_cif cell (may be primitive)",
              "site_count": len(mof.structure), "index_base": 0,
              "library_versions": {"pymatgen": version("pymatgen"),
                                   "moffragmentor": version("moffragmentor")}, **fields}
    return _finite_json(result)


def get_mof_lattice(cif_file_name: str) -> dict:
    """Read the default MOF cell lattice (possibly primitive), with angstrom/degree/angstrom^3 units and exact CIF source hash."""
    mof, path, digest = _mof(cif_file_name, graph_required=False)
    lattice = mof.lattice
    return _mof_result(mof, path, digest, cell_angstrom=lattice.matrix.tolist(),
        lengths_angstrom=list(lattice.abc), angles_degrees=list(lattice.angles),
        volume_angstrom_cubed=float(lattice.volume), pbc=list(lattice.pbc))


def get_mof_fractional_coordinates(cif_file_name: str) -> dict:
    """Return full-precision fractional site coordinates in the default MOF cell with zero-based indices; no supplied-cell equivalence is assumed."""
    mof, path, digest = _mof(cif_file_name, graph_required=False)
    return _mof_result(mof, path, digest, fractional_coordinates=mof.frac_coords.tolist())


def get_neighbor_indices(cif_file_name: str, site_index: int) -> dict:
    """Return bonded MOF-graph neighbor indices for one zero-based default-cell site; not a radius/geometric neighbor search."""
    if type(site_index) is not int:
        raise ValueError("site_index must be an integer, not a boolean")
    mof, path, digest = _mof(cif_file_name)
    if not 0 <= site_index < len(mof.structure):
        raise ValueError("site_index is outside the default MOF-cell site range")
    return _mof_result(mof, path, digest, site_index=site_index,
        neighbor_indices=[int(v) for v in mof.get_neighbor_indices(site_index)],
        method="moffragmentor default chemical-bond graph")


def get_symbol_of_site(cif_file_name: str, site: int) -> dict:
    """Return the element symbol of one zero-based site in the default MOF cell; indices refer to that cell, not the unmodified input ordering."""
    if type(site) is not int:
        raise ValueError("site must be an integer, not a boolean")
    mof, path, digest = _mof(cif_file_name, graph_required=False)
    if not 0 <= site < len(mof.structure):
        raise ValueError("site is outside the default MOF-cell range")
    return _mof_result(mof, path, digest, site_index=site, element_symbol=str(mof.structure[site].specie))


def get_bridges(cif_file_name: str) -> dict:
    """Return moffragmentor graph bridge mapping in the default MOF cell; this is distinct from branch-point or degree-one terminal-site analysis."""
    mof, path, digest = _mof(cif_file_name)
    return _mof_result(mof, path, digest, bridges={str(k): [int(v) for v in values] for k, values in mof.bridges.items()})


def get_branch_points(cif_file_name: str) -> dict:
    """Return moffragmentor fragmentor branch-point indices in the default MOF bonding graph."""
    from moffragmentor import fragmentor

    mof, path, digest = _mof(cif_file_name)
    return _mof_result(mof, path, digest,
        branch_indices=[int(v) for v in fragmentor.branching_points.get_branch_points(mof)])


def get_terminal_indices(cif_file_name: str) -> dict:
    """Return degree-one terminal-site indices joined by a bridge in the MOF default-cell chemical graph; no solvent-removal feasibility is inferred."""
    mof, path, digest = _mof(cif_file_name)
    return _mof_result(mof, path, digest, terminal_indices=[int(v) for v in mof.terminal_indices])


def get_floating_solvent_molecules(cif_file_name: str) -> dict:
    """Report composition/counts of finite nonperiodic floating graph components per default MOF cell. No charge, missing-H, solvent identity certainty or stability is inferred."""
    from moffragmentor import fragmentor

    mof, path, digest = _mof(cif_file_name)
    collection = fragmentor.solventlocator.get_floating_solvent_molecules(mof)
    return _mof_result(mof, path, digest, floating_composition_counts=dict(collection.composition),
        component_count=len(collection), method="moffragmentor finite nonperiodic components")


def get_mof_linker_smiles(cif_file_name: str) -> dict:
    """Fragment one MOF and return all identified linker SMILES, not a SMILES for the entire periodic framework or an arbitrary first linker."""
    mof, path, digest = _mof(cif_file_name)
    fragments = mof.fragment()
    linkers = [{"linker_index": index, "smiles": str(linker.smiles)}
               for index, linker in enumerate(fragments.linkers)]
    return _mof_result(mof, path, digest, linkers=linkers,
        scope="Linker fragments only; fragmentation/bond perception can be ambiguous")


def plot_adjacency_matrix(cif_file_name: str) -> dict:
    """Render the MOF default-cell graph adjacency as PNG; periodic image identity is collapsed by matrix conversion and is not a bond-length/geometry measurement."""
    import io
    import base64
    import networkx as nx
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    mof, path, digest = _mof(cif_file_name)
    if len(mof.structure) > 500:
        raise ValueError("Adjacency image is limited to500sites; no matrix is silently downsampled")
    matrix = nx.to_numpy_array(mof.structure_graph.graph)
    figure, axis = plt.subplots()
    try:
        axis.imshow(matrix)
        axis.set_title("Default-cell MOF graph adjacency")
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", bbox_inches="tight")
    finally:
        plt.close(figure)
    return _mof_result(mof, path, digest,
        image_png="data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
        representation="NetworkX adjacency; periodic image identities are collapsed")
