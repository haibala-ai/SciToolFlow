"""Occupancy-preserving inventories from observed crystal-parser objects."""

import math
import re
from .values import MissingEvidence, _number


def crystal_density_inventory(value):
    """Read unreduced cell populations from a provenance-bearing density receipt.

    CalculateDensity emits pymatgen Composition.formula, with an explicit count
    for every element. This is a separate contract from a molecular formula:
    fractional occupancies and cell multiplicity must survive unchanged. Call
    matching must additionally bind the tool and the expected source SHA256.
    """
    method = "pymatgen static periodic-cell density; occupancy-weighted cell mass / cell volume"
    if (not isinstance(value, dict) or value.get("method") != method
            or not isinstance(value.get("source_file"), str) or not value["source_file"]
            or not isinstance(value.get("source_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", value["source_sha256"])
            or type(value.get("sites")) is not int or not 1 <= value["sites"] <= 1000000
            or any(not _number(value.get(k)) or value[k] <= 0
                   for k in ("density_g_per_cm3", "mass_u", "volume_angstrom_cubed"))):
        raise MissingEvidence("Require the complete observed static-cell density receipt")
    if not math.isclose(value["density_g_per_cm3"],
                        1.66053906660 * value["mass_u"] / value["volume_angstrom_cubed"],
                        rel_tol=1e-6, abs_tol=1e-10):
        raise MissingEvidence("Density, supplied cell mass and volume conflict")
    formula = value.get("formula")
    if not isinstance(formula, str) or not 1 <= len(formula) <= 4096:
        raise MissingEvidence("Require an explicit unreduced cell formula")
    inventory = {}
    for token in formula.split():
        match = re.fullmatch(r"([A-Z][a-z]?)([0-9]+(?:\.[0-9]+)?)", token)
        if match is None or match[1] in inventory:
            raise MissingEvidence("Cell formula must contain distinct explicit element counts")
        count = float(match[2])
        if not math.isfinite(count) or count <= 0:
            raise MissingEvidence("Cell population must be finite and positive")
        inventory[match[1]] = count
    if (not 1 <= len(inventory) <= 118
            or sum(inventory.values()) > value["sites"] + 1e-6 * value["sites"]):
        raise MissingEvidence("Cell populations exceed the observed site inventory")
    if "element_amounts" in value or "structure" in value:
        other = crystal_element_inventory(value)
        if set(other) != set(inventory) or any(not math.isclose(
                other[k], inventory[k], rel_tol=1e-8, abs_tol=1e-8) for k in other):
            raise MissingEvidence("Conflicting density and structure inventories")
    return inventory


def crystal_element_inventory(value):
    if not isinstance(value, dict):
        raise MissingEvidence("Crystal inventory requires an observed parser object")
    amounts=None
    if "element_amounts" in value:
        amounts = value["element_amounts"]
        if (not isinstance(amounts, dict) or not 1 <= len(amounts) <= 118
                or any(not isinstance(k, str) or not re.fullmatch(r"[A-Z][a-z]?", k)
                       or not _number(v) or v <= 0 for k, v in amounts.items())):
            raise MissingEvidence("Invalid observed element amounts")
        if 'structure'not in value:return dict(amounts)
    structure = value.get("structure")
    sites = structure.get("sites") if isinstance(structure, dict) else None
    if not isinstance(sites, list) or not 1 <= len(sites) <= 10000:
        raise MissingEvidence("Require actual parsed structure sites")
    inventory, entries = {}, 0
    for site in sites:
        species = site.get("species") if isinstance(site, dict) else None
        if not isinstance(species, list) or not 1 <= len(species) <= 118:
            raise MissingEvidence("Require actual species/occupancy entries")
        total, seen = 0.0, set()
        for row in species:
            entries += 1
            if (not isinstance(row, dict) or not isinstance(row.get("element"), str)
                    or not re.fullmatch(r"[A-Z][a-z]?", row["element"])
                    or row["element"] in seen or not _number(row.get("occu"))
                    or not 0 < row["occu"] <= 1 or entries > 20000):
                raise MissingEvidence("Invalid or excessive species inventory")
            element, occupancy = row["element"], row["occu"]
            seen.add(element)
            total += occupancy
            inventory[element] = inventory.get(element, 0.0) + occupancy
        if total > 1 + 1e-8:
            raise MissingEvidence("Overoccupied source site")
    if not all(math.isfinite(v) and v > 0 for v in inventory.values()):
        raise MissingEvidence("Nonfinite source inventory")
    if amounts is not None and (set(amounts)!=set(inventory)or any(
            not math.isclose(amounts[k],inventory[k],rel_tol=1e-8,abs_tol=1e-8)for k in amounts)):
        raise MissingEvidence('Conflicting element inventory and observed structure sites')
    return inventory
