"""Scientific cell/occupancy scaling, source binding and explicit failure tests."""

import hashlib
import tempfile
from pathlib import Path
import unittest

from tools.implementations.materials.basic_local import calculate_density


class CrystalDensityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cell(self, name, side=5, occupancy=1):
        path = self.root / name
        path.write_text(
            f"""data_test
_cell_length_a {side}
_cell_length_b {side}
_cell_length_c {side}
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
Si1 Si 0 0 0 {occupancy}
"""
        )
        return path

    def test_full_precision_mass_volume_and_exact_source(self):
        p = self.cell("silicon.cif")
        v = calculate_density(str(p))
        self.assertAlmostEqual(v["mass_u"], 28.0855, places=6)
        self.assertAlmostEqual(v["volume_angstrom_cubed"], 125, places=10)
        self.assertAlmostEqual(
            v["density_g_per_cm3"], 28.0855 * 1.660539067 / 125, places=9
        )
        self.assertNotEqual(v["density_g_per_cm3"], round(v["density_g_per_cm3"], 2))
        self.assertEqual(v["source_sha256"], hashlib.sha256(p.read_bytes()).hexdigest())

    def test_unit_cell_length_and_occupancy_scaling(self):
        a = calculate_density(str(self.cell("base.cif")))
        b = calculate_density(str(self.cell("dilated.cif", side=10)))
        c = calculate_density(str(self.cell("occupancy.cif", occupancy=0.5)))
        self.assertAlmostEqual(
            a["density_g_per_cm3"] / 8, b["density_g_per_cm3"], places=13
        )
        self.assertAlmostEqual(
            a["density_g_per_cm3"] / 2, c["density_g_per_cm3"], places=13
        )

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            calculate_density(str(self.root / "missing.cif"))

    def test_malformed_file_raises_instead_of_successful_error_text(self):
        p = self.root / "invalid.cif"
        p.write_text("not a structure")
        with self.assertRaisesRegex(
            ValueError, "Cannot calculate periodic-cell density"
        ):
            calculate_density(str(p))


if __name__ == "__main__":
    unittest.main()
