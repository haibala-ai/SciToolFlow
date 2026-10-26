"""CIF source coordinates determine geometry even close to ideal fractions."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.implementations.materials.research_workflows import (
    _structure,
    matched_periodic_displacements,
    periodic_neighbor_list,
)


class CifCoordinateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.allow = patch(
            "tools.implementations.general.research_data._public_source_path",
            side_effect=Path,
        )
        self.allow.start()

    def tearDown(self):
        self.allow.stop()
        self.tmp.cleanup()

    def cell(self, name, coordinate):
        p = self.root / name
        p.write_text(
            f"""data_test
_cell_length_a 10
_cell_length_b 10
_cell_length_c 10
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_symmetry_equiv_pos_as_xyz
'x,y,z'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
C1 C 0 0 0 1
Si1 Si {coordinate} 0 0 1
"""
        )
        return p

    def test_explicit_coordinate_not_replaced_by_exact_one_third(self):
        p = self.cell("source.cif", 0.333333)
        s, _, _ = _structure(str(p))
        site = next(v for v in s if str(v.specie) == "Si")
        self.assertEqual(site.frac_coords[0], 0.333333)
        self.assertNotEqual(site.frac_coords[0], 1 / 3)

    def test_cutoff_between_source_and_idealized_distances(self):
        p = self.cell("source.cif", 0.333333)
        o = periodic_neighbor_list(str(p), 3.333331)
        self.assertEqual(o["edge_count"], 2)
        for e in o["neighbors"]:
            self.assertAlmostEqual(e["distance_angstrom"], 3.33333, places=11)
        self.assertEqual(periodic_neighbor_list(str(p), 3.333328)["edge_count"], 0)

    def test_small_real_displacement_not_erased_by_snapping_both_sites(self):
        a = self.cell("a.cif", 0.333333)
        b = self.cell("b.cif", 0.333334)
        o = matched_periodic_displacements(str(a), str(b))
        row = next(v for v in o["displacements"] if v["species"] == "Si")
        self.assertAlmostEqual(row["distance_angstrom"], 0.00001, places=12)


if __name__ == "__main__":
    unittest.main()
