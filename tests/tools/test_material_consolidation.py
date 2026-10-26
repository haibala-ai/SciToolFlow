"""Material selector, identity, scientific-scope and source-integrity regression tests.

HTTP fixtures below are explicitly synthetic protocol controls, not evidence of
service availability. Real API and author-resource checks are recorded separately.
"""

import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.implementations.materials import material_queries as q
from tools.implementations.materials import local_queries as local
from tools.implementations.materials.basic_local import calculate_density, convert_units
from tools.implementations.shared.materials_api import MissingScientificData

MOL = "042b6da7a6eb790fd5038f3729ef715c-C5H8O3-m1-2"


def response(records, total=None):
    payload = {
        "data": records,
        "meta": {
            "api_version": "synthetic-control",
            "time_stamp": "control",
            "total_doc": len(records) if total is None else total,
        },
    }
    return SimpleNamespace(json=lambda: payload)


class SelectorTests(unittest.TestCase):
    def test_invalid_selectors_do_not_make_requests(self):
        with patch.object(q.materials_api, "get") as get:
            for kwargs in [
                {},
                {"material_id": "mp-149", "formula": "Si"},
                {"material_ids": ["mp-149"]},
                {"material_id": "mp-149.mp-13"},
                {"formula": "Si,*"},
                {"material_id": "mp-149", "offset": 1},
            ]:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    q.get_material_band_gap(**kwargs)
            get.assert_not_called()

    def test_formula_preserves_polymorphs_zero_and_missing_value(self):
        rows = [
            {"material_id": "mp-aaaaaaaa", "band_gap": 0.0},
            {"material_id": "mp-aaaaaaab", "band_gap": None},
            {"material_id": "mp-aaaaaaac", "band_gap": 2.1},
        ]
        with patch.object(
            q.materials_api, "get", return_value=response(rows, 3)
        ) as get:
            result = q.get_material_band_gap(formula="Si", limit=2)
        self.assertEqual(
            [r["material_id"] for r in result["records"]],
            ["mp-aaaaaaaa", "mp-aaaaaaab"],
        )
        self.assertTrue(result["records"][0]["available"])
        self.assertEqual(result["records"][0]["value"], 0.0)
        self.assertFalse(result["records"][1]["available"])
        self.assertTrue(result["pagination"]["has_more"])
        self.assertEqual(result["pagination"]["next_offset"], 2)
        self.assertEqual(get.call_args.kwargs["params"]["_limit"], 3)

    def test_legacy_alias_resolution_is_reported_not_assigned_by_order(self):
        with patch.object(
            q.materials_api,
            "get",
            return_value=response([{"material_id": "mp-aaaaaaft", "band_gap": 0.61}]),
        ):
            result = q.get_material_band_gap(material_id="mp-149")
        self.assertEqual(result["selector"], {"material_ids": "mp-149"})
        self.assertEqual(result["records"][0]["material_id"], "mp-aaaaaaft")

    def test_canonical_batch_is_one_request_and_associates_by_identity(self):
        ids = ["mp-aaaaaaaa", "mp-aaaaaaab"]
        with patch.object(
            q.materials_api,
            "get",
            return_value=response(
                [
                    {"material_id": ids[1], "band_gap": 1.2},
                    {"material_id": ids[0], "band_gap": 0.0},
                ]
            ),
        ) as get:
            result = q.get_material_band_gap(material_ids=ids)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs["params"]["material_ids"], ",".join(ids))
        self.assertEqual(
            {r["material_id"]: r["value"] for r in result["records"]},
            {ids[1]: 1.2, ids[0]: 0.0},
        )
        self.assertEqual(result["missing_requested_ids"], [])

    def test_foreign_batch_record_and_ambiguous_single_record_fail(self):
        with patch.object(
            q.materials_api,
            "get",
            return_value=response([{"material_id": "mp-aaaaaaaz", "band_gap": 1}]),
        ):
            with self.assertRaisesRegex(RuntimeError, "identity"):
                q.get_material_band_gap(material_ids=["mp-aaaaaaaa"])
        with patch.object(
            q.materials_api,
            "get",
            return_value=response(
                [
                    {"material_id": "mp-aaaaaaaa", "band_gap": 1},
                    {"material_id": "mp-aaaaaaab", "band_gap": 2},
                ]
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "multiple"):
                q.get_material_band_gap(material_id="mp-149")

    def test_missing_single_field_is_not_success(self):
        with patch.object(
            q.materials_api,
            "get",
            return_value=response([{"material_id": "mp-aaaaaaft", "band_gap": None}]),
        ):
            with self.assertRaises(MissingScientificData):
                q.get_material_band_gap(material_id="mp-149")

    def test_physical_quantities_and_units_remain_distinct(self):
        queried = []

        def protocol(url, **kwargs):
            fields = kwargs["params"]["_fields"].split(",")
            field = fields[1]
            queried.append(field)
            return response([{"material_id": "mp-aaaaaaft", field: 2.0}])

        with patch.object(q.materials_api, "get", side_effect=protocol):
            density = q.get_material_density(material_id="mp-149")
            packing = q.get_material_density_atomic(material_id="mp-149")
            dielectric = q.get_material_e_total(material_id="mp-149")
        self.assertEqual(queried, ["density", "density_atomic", "e_total"])
        self.assertEqual(density["units"], "g/cm^3")
        self.assertEqual(packing["units"], "angstrom^3/atom")
        self.assertEqual(dielectric["units"], "dimensionless")

    def test_search_is_id_discovery_with_explicit_stability(self):
        with patch.object(q.materials_api, "get", return_value=response([])) as get:
            result = q.search_materials(chemsys="O-Si")
        self.assertEqual(result["material_ids"], [])
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["chemsys"], "O-Si")
        self.assertEqual(params["_fields"], "material_id")
        self.assertNotIn("is_stable", params)

    def test_deprecated_record_is_not_hidden_by_default_false_filter(self):
        with patch.object(
            q.materials_api,
            "get",
            side_effect=[
                response([]),
                response([{"material_id": "mp-aaaaaaaa", "deprecated": True}]),
            ],
        ) as get:
            result = q.get_material_deprecation_status("mp-1")
        self.assertEqual(get.call_count, 2)
        self.assertFalse(get.call_args_list[0].kwargs["params"]["deprecated"])
        self.assertTrue(get.call_args_list[1].kwargs["params"]["deprecated"])
        self.assertTrue(result["records"][0]["value"])


class MoleculeScopeTests(unittest.TestCase):
    def test_solvent_method_and_native_energy_units_are_preserved(self):
        record = {
            "molecule_id": MOL,
            "thermo": {
                "NONE": {
                    "electronic_energy": -15,
                    "level_of_theory": "vacuum-method",
                    "property_id": "p1",
                },
                "WATER": {
                    "electronic_energy": -16,
                    "level_of_theory": "solvent-method",
                    "property_id": "p2",
                },
            },
        }
        with patch.object(q.materials_api, "get", return_value=response([record])):
            result = q.get_molecular_electronic_energy(MOL)
        self.assertEqual(result["units"], "eV")
        self.assertEqual(result["value"]["NONE"]["value"], -15)
        self.assertEqual(result["value"]["WATER"]["property_id"], "p2")
        self.assertEqual(result["value"]["WATER"]["level_of_theory"], "solvent-method")

    def test_component_is_not_substituted_by_total(self):
        record = {"molecule_id": MOL, "thermo": {"NONE": {"total_enthalpy": 3.5}}}
        with patch.object(q.materials_api, "get", return_value=response([record])):
            with self.assertRaises(MissingScientificData):
                q._molecule("translational_enthalpy", "eV", MOL, group="thermo")

    def test_local_frequency_route_does_not_lookup_an_unrelated_molecule(self):
        with (
            patch.object(
                q, "_qchem", return_value={"backend": "test-parser-control"}
            ) as local_parse,
            patch.object(q.materials_api, "get") as get,
        ):
            result = q.get_molecular_frequencies(qchem_file="supplied.qout")
        local_parse.assert_called_once_with("frequencies", "supplied.qout")
        get.assert_not_called()
        self.assertEqual(result["backend"], "test-parser-control")

    def test_charge_density_selector_is_exclusive(self):
        with self.assertRaises(ValueError):
            q.resolve_charge_density_metadata(task_id="mp-1", fs_id="0" * 24)


class LocalScientificTests(unittest.TestCase):
    def test_skew_cell_minimum_image_beyond_adjacent_images_and_ties(self):
        from pymatgen.core import Lattice, Structure
        from tools.implementations.materials.research_workflows import (
            matched_periodic_displacements,
        )

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cell = Lattice([[1, 0, 0], [10, 1, 0], [0, 0, 1]])
            a, b = root / "reference.vasp", root / "mobile.vasp"
            Structure(cell, ["Si"], [[0, 0, 0]]).to(filename=a, fmt="poscar")
            Structure(cell, ["Si"], [[0.49, 0.49, 0]]).to(filename=b, fmt="poscar")
            with patch(
                "tools.implementations.general.research_data._public_source_path",
                side_effect=Path,
            ):
                row = matched_periodic_displacements(str(a), str(b))["displacements"][0]
            self.assertEqual(row["image_shift"], [-5, 0, 0])
            self.assertAlmostEqual(
                row["minimum_distance_angstrom"], math.hypot(0.39, 0.49), places=12
            )
            cell = Lattice.cubic(2)
            Structure(cell, ["Si"], [[0, 0, 0]]).to(filename=a, fmt="poscar")
            Structure(cell, ["Si"], [[0.5, 0, 0]]).to(filename=b, fmt="poscar")
            with patch(
                "tools.implementations.general.research_data._public_source_path",
                side_effect=Path,
            ):
                row = matched_periodic_displacements(str(a), str(b))["displacements"][0]
            self.assertEqual(row["image_shift"], [-1, 0, 0])
            self.assertEqual(row["tie_count"], 2)
            self.assertFalse(row["minimum_image_unique"])

    def test_source_geometry_density_and_composition_have_distinct_contracts(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "source.cif"
            path.write_text(
                """data_source
_cell_length_a 5
_cell_length_b 5
_cell_length_c 5
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0.333333 0 0 1
"""
            )
            geometry = local.read_crystal_structure(str(path))
            composition = local.get_element_composition(str(path))
            density = calculate_density(str(path))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(geometry["source_sha256"], digest)
            self.assertEqual(geometry["structure"]["sites"][0]["abc"][0], 0.333333)
            self.assertEqual(
                geometry["structure"]["lattice"]["pbc"], [True, True, True]
            )
            from tools.runtime.dispatch import validate_result

            contract = {
                "output_schema": {
                    "type": "object",
                    "required": ["structure", "source_sha256"],
                    "properties": {
                        "structure": {"type": "object"},
                        "source_sha256": {"type": "string"},
                    },
                }
            }
            self.assertEqual(validate_result(geometry, contract)["status"], "success")
            self.assertNotIn("density_g_per_cm3", geometry)
            self.assertEqual(composition["element_amounts"], {"Si": 1.0})
            self.assertAlmostEqual(
                density["density_g_per_cm3"],
                density["mass_u"] * 1.660539067 / 125,
                places=9,
            )

    def test_json_adapter_preserves_native_numeric_values_and_rejects_nonfinite(self):
        import numpy as np
        from tools.runtime.dispatch import validate_result

        source = {
            "pbc": (np.bool_(True), False, True),
            "coordinates": np.array([[0.125, 2.5, -3.0]]),
            "sites": np.int64(1),
        }
        normalized = local._finite_json(source)
        self.assertEqual(
            normalized,
            {
                "pbc": [True, False, True],
                "coordinates": [[0.125, 2.5, -3.0]],
                "sites": 1,
            },
        )
        self.assertEqual(
            validate_result(normalized, {"output_schema": {"type": "object"}})[
                "status"
            ],
            "success",
        )
        self.assertEqual(
            validate_result(source, {"output_schema": {"type": "object"}})[
                "error_type"
            ],
            "InvalidOutput",
        )
        with self.assertRaises(ValueError):
            local._finite_json({"coordinate": np.float64("nan")})
        with self.assertRaises(TypeError):
            local._finite_json({"coordinate": object()})

    def test_bad_local_inputs_and_nonfinite_units_fail(self):
        with self.assertRaises(FileNotFoundError):
            local.read_crystal_structure("/not/a/real/structure.cif")
        with self.assertRaises(ValueError):
            local.calculate_symmetry("unused.cif", symprec=float("nan"))
        with self.assertRaises(ValueError):
            convert_units("1e999 meter to centimeter")


if __name__ == "__main__":
    unittest.main()
