"""Small local material primitives; no live API, inference service or experiment."""

import hashlib
import math
from importlib.metadata import version
from pathlib import Path


def _structure(file_name):
    from pymatgen.core import Structure
    from tools.implementations.general.research_data import _public_source_path

    path = _public_source_path(file_name)
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Structure inputs are limited to 10 MiB")
    raw = path.read_bytes()
    # Preserve explicitly supplied CIF fractional positions. The parser's
    # default rational snapping can change distances near a requested cutoff.
    structure = (
        Structure.from_file(path, frac_tolerance=0)
        if path.name.lower().endswith((".cif", ".mcif", ".cif.gz", ".mcif.gz"))
        else Structure.from_file(path)
    )
    if not structure.is_ordered:
        raise ValueError("Disordered/partial occupancy structures are unsupported")
    if (
        not 1 <= len(structure) <= 1000
        or not math.isfinite(structure.volume)
        or structure.volume <= 0
    ):
        raise ValueError(
            "Structure requires 1 to 1000 ordered sites and finite positive volume"
        )
    if path.read_bytes() != raw:
        raise ValueError("Structure source changed during parsing")
    return structure, path.name, hashlib.sha256(raw).hexdigest()


def crystal_structure_match(
    structure_a: str,
    structure_b: str,
    primitive_cell: bool = True,
    scale: bool = False,
    lattice_tolerance: float = 0.2,
    site_tolerance: float = 0.3,
    angle_tolerance_deg: float = 5.0,
) -> dict:
    """Compare two public crystal files under explicit geometric equivalence.

    CIF fractional positions are preserved without rational-coordinate snapping.

    Args:
        structure_a (str): First uploaded ordered structure file (CIF/POSCAR).
        structure_b (str): Second uploaded ordered structure file.
        primitive_cell (bool): Reduce both inputs to primitive cells before match.
        scale (bool): Whether isotropic cell-volume rescaling is permitted.
        lattice_tolerance (float): Fractional lattice-length tolerance, (0,0.5].
        site_tolerance (float): Site tolerance as fraction of average free length,
            (0,1]; NOT a displacement tolerance expressed in angstrom.
        angle_tolerance_deg (float): Lattice-angle tolerance, (0,15] degrees.

    Returns:
        dict: Matched boolean, normalized RMS/max displacement (null if no
            match), formulas, sites/volumes, exact source hashes, settings and
            pymatgen version. Geometric equivalence is not equal thermodynamic
            state or agreement of calculation methods.
    """
    from pymatgen.analysis.structure_matcher import StructureMatcher

    if type(primitive_cell) is not bool or type(scale) is not bool:
        raise ValueError("primitive_cell and scale must be booleans")
    for number, limit, label in [
        (lattice_tolerance, 0.5, "lattice_tolerance"),
        (site_tolerance, 1, "site_tolerance"),
        (angle_tolerance_deg, 15, "angle_tolerance_deg"),
    ]:
        if (
            type(number) not in (int, float)
            or not math.isfinite(number)
            or not 0 < number <= limit
        ):
            raise ValueError(label + " outside supported finite positive range")
    a, name_a, sha_a = _structure(structure_a)
    b, name_b, sha_b = _structure(structure_b)
    matcher = StructureMatcher(
        ltol=lattice_tolerance,
        stol=site_tolerance,
        angle_tol=angle_tolerance_deg,
        primitive_cell=primitive_cell,
        scale=scale,
        attempt_supercell=False,
        allow_subset=False,
    )
    rms = matcher.get_rms_dist(a, b)
    return {
        "matched": rms is not None,
        "normalized_rms_displacement": float(rms[0]) if rms else None,
        "normalized_max_displacement": float(rms[1]) if rms else None,
        "displacement_basis": "normalized by (volume/sites)^(1/3); not angstrom",
        "formula_a": a.composition.reduced_formula,
        "formula_b": b.composition.reduced_formula,
        "sites_a": len(a),
        "sites_b": len(b),
        "volume_a_ang3": float(a.volume),
        "volume_b_ang3": float(b.volume),
        "source_a": name_a,
        "source_b": name_b,
        "source_sha256_a": sha_a,
        "source_sha256_b": sha_b,
        "settings": {
            "primitive_cell": primitive_cell,
            "scale": scale,
            "lattice_tolerance": lattice_tolerance,
            "site_tolerance": site_tolerance,
            "angle_tolerance_deg": angle_tolerance_deg,
        },
        "pymatgen_version": version("pymatgen"),
        "limitations": [
            "No subset, disordered occupancy, magnetic-order or method comparison",
            "Matching alone does not establish equal pressure/temperature or energy",
        ],
    }


def powder_diffraction_pattern(
    structure_file: str,
    wavelength_angstrom: float = 1.5406,
    two_theta_min_deg: float = 10.0,
    two_theta_max_deg: float = 80.0,
) -> dict:
    """Compute one ideal powder X-ray pattern from an ordered public structure.

    CIF fractional positions are preserved without rational-coordinate snapping.

    Args:
        structure_file (str): Uploaded ordered structure file (CIF/POSCAR).
        wavelength_angstrom (float): Positive X-ray wavelength in [0.1,5] angstrom.
        two_theta_min_deg (float): Lower two-theta angle in [0,179) degrees.
        two_theta_max_deg (float): Upper two-theta angle above lower and <=179.

    Returns:
        dict: Peak records (two_theta_deg, relative_intensity, d_spacing_angstrom,
            and Miller-index families), wavelength/range, source hash/formula and
            pymatgen version. Intensities are normalized to maximum100; a valid
            range with no reflections returns an empty peak list. This ideal
            kinematic calculation omits instrumental broadening and texture.
    """
    from pymatgen.analysis.diffraction.xrd import XRDCalculator

    for value in [wavelength_angstrom, two_theta_min_deg, two_theta_max_deg]:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Wavelength and angular bounds must be finite numbers")
    if (
        not 0.1 <= wavelength_angstrom <= 5
        or not 0 <= two_theta_min_deg < two_theta_max_deg <= 179
    ):
        raise ValueError("Unsupported wavelength or two-theta range")
    structure, name, sha = _structure(structure_file)
    try:
        pattern = XRDCalculator(wavelength=wavelength_angstrom, symprec=0).get_pattern(
            structure, two_theta_range=(two_theta_min_deg, two_theta_max_deg)
        )
    except ValueError as error:
        # pymatgen v2025.10.7 takes max(peaks.values()) before checking whether
        # any reciprocal-lattice reflection lies in the requested range.
        # This specific upstream empty-sequence case is a valid empty pattern;
        # preserve other input/calculation failures as errors.
        if str(error) != "max() arg is an empty sequence":
            raise
        pattern = None
    if pattern is not None and len(pattern.x) > 5000:
        raise ValueError("Pattern exceeds5000 peaks; use a narrower angular range")
    peaks = [
        {
            "two_theta_deg": float(x),
            "relative_intensity": float(y),
            "d_spacing_angstrom": float(d),
            "hkls": [
                {
                    "hkl": [int(v) for v in family["hkl"]],
                    "multiplicity": int(family["multiplicity"]),
                }
                for family in families
            ],
        }
        for x, y, d, families in (
            zip(pattern.x, pattern.y, pattern.d_hkls, pattern.hkls)
            if pattern is not None
            else []
        )
    ]
    return {
        "peaks": peaks,
        "peak_count": len(peaks),
        "wavelength_angstrom": wavelength_angstrom,
        "two_theta_range_deg": [two_theta_min_deg, two_theta_max_deg],
        "formula": structure.composition.reduced_formula,
        "source_file": name,
        "source_sha256": sha,
        "pymatgen_version": version("pymatgen"),
        "limitations": [
            "Ideal kinematic powder pattern; no instrumental broadening, preferred orientation, disorder or quantitative phase-fraction validation"
        ],
    }


def composition_fractions(formula: str) -> dict:
    """Report elemental atom/mass fractions of an explicit positive composition.

    Args:
        formula (str): Chemical formula understood by pymatgen Composition; no
            automatic oxidation-state, charge-balance or phase inference.

    Returns:
        dict: Reduced formula, original atom amounts, total atom count,
            atomic/mass fractions and formula mass in u (numerically g/mol).
            Values describe the stated formula, not an experimentally pure phase.
    """
    from pymatgen.core import Composition

    if not isinstance(formula, str) or not formula.strip() or len(formula) > 1000:
        raise ValueError("formula must be a nonempty string of at most1000 characters")
    comp = Composition(formula, strict=True)
    if not comp or any(
        not math.isfinite(float(v)) or float(v) <= 0 for v in comp.values()
    ):
        raise ValueError("Composition must contain finite positive atom amounts")
    return {
        "reduced_formula": comp.reduced_formula,
        "element_amounts": {
            str(k): float(v) for k, v in comp.element_composition.items()
        },
        "total_atom_count": float(comp.num_atoms),
        "atomic_fractions": {
            el.symbol: float(comp.get_atomic_fraction(el)) for el in comp.elements
        },
        "mass_fractions": {
            el.symbol: float(comp.get_wt_fraction(el)) for el in comp.elements
        },
        "formula_mass_u": float(comp.weight),
        "pymatgen_version": version("pymatgen"),
        "limitations": [
            "No oxidation-state, charge-balance, purity or phase-stability inference"
        ],
    }


def periodic_neighbor_list(structure_file: str, cutoff_angstrom: float) -> dict:
    """Return all directed periodic geometric neighbors in a finite radius.

    CIF fractional positions are preserved without rational-coordinate snapping.

    Args:
        structure_file: Explicitly uploaded ordered crystal file, same public
            allowlist and10MiB source limit as the other crystal primitives.
        cutoff_angstrom: Finite positive Cartesian radius<=10angstrom. Search
            uses pymatgen's periodic neighbor algorithm, including image shifts
            beyond[-1,1] when required by an oblique cell. At most256 source
            sites and10000 returned directed edges; estimated candidate work
            N²*product(2*ceil((cutoff+1e-8)/h_i)+3) must be<=1000000,where h_i
            are perpendicular cell heights. Excess work/edges reject the whole
            call before return; results are never truncated to the edge limit.

    Returns:
        dict with neighbors(list of unique edge_id,center_index,neighbor_index,image_shift,
        distance_angstrom,displacement_angstrom),edge_count,source SHA/formula,
        species,cell_angstrom,cutoff_angstrom,boundary_tolerance_angstrom,
        candidate_pair_bound andscope. Cell vectors are rows. Displacement is
        r_neighbor+image_shift@cell-r_center (center to neighbor-image).
        The list is directed: reverse edges are retained,and same-atom nonzero
        images are valid neighbors. Only the exact self pair with zero image
        is removed; coincident distinct sites are not silently discarded.
        Distances<=cutoff+1e-8angstrom are included. No chemical bonding,
        coordination-shell,oxidation-state or nearest-neighbor interpretation.

    Raises:
        ValueError: Unsupported type/radius,disorder,too many sites or images,
            near-singular/nonfinite cell,nonfinite or abs>1e6 fractional
            coordinates,numerical failure or>10000 edges.
    """
    import numpy as np
    from threadpoolctl import threadpool_limits

    if (
        type(cutoff_angstrom) not in (int, float)
        or not math.isfinite(cutoff_angstrom)
        or not 0 < cutoff_angstrom <= 10
    ):
        raise ValueError("cutoff_angstrom must be finite,positive and<=10")
    structure, name, digest = _structure(structure_file)
    if len(structure) > 256:
        raise ValueError("Periodic neighborhood supports at most256 source sites")
    cell = np.asarray(structure.lattice.matrix, dtype=float)
    reciprocal = np.asarray(
        structure.lattice.reciprocal_lattice_crystallographic.lengths
    )
    if (
        not np.all(np.isfinite(cell))
        or not np.all(np.isfinite(reciprocal))
        or np.any(reciprocal <= 0)
        or structure.volume < 1e-8
    ):
        raise ValueError("Finite nonsingular cell required,volume>=1e-8angstrom³")
    heights = 1 / reciprocal
    if np.min(heights) < 1e-5:
        raise ValueError("Near-singular cell height below1e-5angstrom is unsupported")
    tolerance = 1e-8
    # Fractional sites are wrapped to[0,1) by the search representation. The
    # reciprocal-height bound covers possible fractional differences<1 plus
    # cutoff/h,including skew cells requiring image shifts beyond one cell.
    widths = [
        2 * (math.ceil((cutoff_angstrom + tolerance) / float(h))) + 3 for h in heights
    ]
    candidate_bound = len(structure) ** 2 * math.prod(widths)
    if candidate_bound > 1000000:
        raise ValueError("Estimated periodic candidate pair bound exceeds1000000")
    fractional = np.asarray(structure.frac_coords, dtype=float)
    if not np.all(np.isfinite(fractional)) or np.max(np.abs(fractional)) > 1e6:
        raise ValueError("Finite fractional source coordinates with abs<=1e6 required")
    offsets = np.floor(fractional).astype(int)
    from pymatgen.core import Structure

    wrapped = Structure(structure.lattice, structure.species, fractional - offsets)
    with threadpool_limits(limits=1):
        centers, neighbors, images, distances = wrapped.get_neighbor_list(
            float(cutoff_angstrom), numerical_tol=tolerance, exclude_self=False
        )
    keep = []
    for center, neighbor, image, distance in zip(centers, neighbors, images, distances):
        image = np.asarray(image)
        if not np.all(np.isfinite(image)) or not np.allclose(
            image, np.rint(image), atol=1e-10, rtol=0
        ):
            raise ValueError("Nonintegral periodic image returned by geometry backend")
        image = (
            np.rint(image).astype(int) + offsets[int(center)] - offsets[int(neighbor)]
        )
        if int(center) == int(neighbor) and np.all(image == 0):
            continue
        if not math.isfinite(float(distance)):
            raise ValueError("Nonfinite periodic neighbor distance")
        if distance > cutoff_angstrom + tolerance:
            continue
        displacement = (
            structure[int(neighbor)].coords
            + image @ cell
            - structure[int(center)].coords
        )
        if not np.all(np.isfinite(displacement)):
            raise ValueError("Nonfinite periodic displacement")
        keep.append(
            {
                "edge_id": str(int(center))
                + ":"
                + str(int(neighbor))
                + ":"
                + ",".join(str(int(v)) for v in image),
                "center_index": int(center),
                "neighbor_index": int(neighbor),
                "image_shift": image.tolist(),
                "distance_angstrom": float(distance),
                "displacement_angstrom": displacement.tolist(),
            }
        )
        if len(keep) > 10000:
            raise ValueError("Periodic neighbor output exceeds10000 directed edges")
    keep.sort(
        key=lambda e: (e["center_index"], e["neighbor_index"], tuple(e["image_shift"]))
    )
    return {
        "neighbors": keep,
        "edge_count": len(keep),
        "source_file": name,
        "source_sha256": digest,
        "formula": structure.composition.formula,
        "site_count": len(structure),
        "species": [str(site.specie) for site in structure],
        "cell_angstrom": cell.tolist(),
        "cutoff_angstrom": float(cutoff_angstrom),
        "boundary_tolerance_angstrom": tolerance,
        "candidate_pair_bound": candidate_bound,
        "scope": "Directed periodic geometric edges only; not chemical bonds or a coordination-shell assignment",
    }


def matched_periodic_displacements(reference_file: str, mobile_file: str) -> dict:
    """Return minimum-image displacements for fixed same-index crystal sites.

    CIF fractional positions are preserved without rational-coordinate snapping.

    Both explicitly uploaded ordered structures must contain the same species
    sequence, 1..256 sites and a common cell (absolute entry tolerance 1e-8 A).
    No atom permutation, rigid alignment, strain removal or trajectory unwrapping
    is performed. Cell rows are lattice vectors. For atom i displacement is
    mobile_cart[i] + image_shift[i] @ reference_cell - reference_cart[i].
    Fractional source coordinates must be finite with abs<=1e6. Volume>=1e-8 A^3
    and perpendicular cell heights>=1e-5 A are required. Exact reciprocal-height
    bounds enumerate at most 1e6 total image candidates; exceeding this rejects
    the entire call before enumeration. No [-1,1] assumption is made for skew
    cells. Images within 1e-8 A of the minimum are treated as tied: the
    lexicographically smallest image is returned, with tie_count and unique flag.
    A half-cell displacement therefore need not have a unique direction.
    Source SHA256 identifies actual input bytes. This geometric primitive does
    not infer diffusion, atomic identity correspondence, or a physical pathway.
    """
    import itertools
    import numpy as np
    from threadpoolctl import threadpool_limits

    reference, reference_name, reference_sha = _structure(reference_file)
    mobile, mobile_name, mobile_sha = _structure(mobile_file)
    species = [str(site.specie) for site in reference]
    if len(reference) > 256 or len(reference) != len(mobile):
        raise ValueError("Same site count in 1..256 is required")
    if species != [str(site.specie) for site in mobile]:
        raise ValueError(
            "Fixed same-index species identities must match exactly; atom matching is not performed"
        )
    cell = np.asarray(reference.lattice.matrix, dtype=float)
    mobile_cell = np.asarray(mobile.lattice.matrix, dtype=float)
    if (
        not np.all(np.isfinite(cell))
        or not np.all(np.isfinite(mobile_cell))
        or not np.allclose(cell, mobile_cell, atol=1e-8, rtol=0)
    ):
        raise ValueError(
            "Finite common cell required, absolute entry tolerance 1e-8 angstrom"
        )
    reciprocal = np.asarray(
        reference.lattice.reciprocal_lattice_crystallographic.lengths, dtype=float
    )
    if (
        reference.volume < 1e-8
        or not np.all(np.isfinite(reciprocal))
        or np.any(reciprocal <= 0)
    ):
        raise ValueError("Nonsingular cell with volume>=1e-8 angstrom^3 required")
    heights = 1 / reciprocal
    if np.min(heights) < 1e-5:
        raise ValueError("Near-singular perpendicular cell height below1e-5 angstrom")
    for structure in (reference, mobile):
        frac = np.asarray(structure.frac_coords, dtype=float)
        if not np.all(np.isfinite(frac)) or np.max(np.abs(frac)) > 1e6:
            raise ValueError("Fractional coordinates must be finite with abs<=1e6")
    tolerance = 1e-8
    with threadpool_limits(limits=1):
        fractional_delta = (
            np.asarray(mobile.cart_coords) - np.asarray(reference.cart_coords)
        ) @ np.linalg.inv(cell)
    if not np.all(np.isfinite(fractional_delta)):
        raise ValueError("Nonfinite fractional displacement")
    searches = []
    candidate_bound = 0
    for delta in fractional_delta:
        offset = np.floor(delta).astype(int)
        wrapped = delta - offset
        upper = float(np.linalg.norm((wrapped - np.rint(wrapped)) @ cell))
        if not math.isfinite(upper):
            raise ValueError("Nonfinite initial distance bound")
        radii = (upper + tolerance) / heights
        lower = np.ceil(-wrapped - radii).astype(int)
        higher = np.floor(-wrapped + radii).astype(int)
        count = math.prod(int(b - a + 1) for a, b in zip(lower, higher))
        candidate_bound += count
        if count < 1 or candidate_bound > 1000000:
            raise ValueError(
                "Estimated image candidate work exceeds1000000 or has invalid bounds"
            )
        searches.append((offset, wrapped, lower, higher))
    rows = []
    with threadpool_limits(limits=1):
        for index, (offset, wrapped, lower, higher) in enumerate(searches):
            minimum = math.inf
            ties = []
            for shift in itertools.product(
                *(range(int(a), int(b) + 1) for a, b in zip(lower, higher))
            ):
                displacement = (wrapped + np.asarray(shift)) @ cell
                distance = float(np.linalg.norm(displacement))
                if not math.isfinite(distance):
                    raise ValueError("Nonfinite periodic displacement distance")
                candidate = (distance,
                             tuple(int(s - o) for s, o in zip(shift, offset)),
                             displacement)
                if distance < minimum:
                    minimum = distance
                    ties = [row for row in ties if row[0] <= minimum + tolerance]
                if distance <= minimum + tolerance:
                    ties.append(candidate)
            distance, image, displacement = min(ties, key=lambda row: row[1])
            rows.append(
                {
                    "atom_index": index,
                    "species": species[index],
                    "image_shift": list(image),
                    "displacement_angstrom": displacement.tolist(),
                    "distance_angstrom": distance,
                    "minimum_distance_angstrom": minimum,
                    "tie_count": len(ties),
                    "minimum_image_unique": len(ties) == 1,
                }
            )
    return {
        "displacements": rows,
        "site_count": len(reference),
        "species": species,
        "cell_angstrom": cell.tolist(),
        "reference_source_file": reference_name,
        "mobile_source_file": mobile_name,
        "reference_source_sha256": reference_sha,
        "mobile_source_sha256": mobile_sha,
        "tie_tolerance_angstrom": tolerance,
        "cell_tolerance_angstrom": 1e-8,
        "image_candidate_bound": candidate_bound,
        "scope": "Fixed-index same-cell minimum-image geometry; no atom matching, alignment, strain removal, diffusion or pathway inference",
    }
