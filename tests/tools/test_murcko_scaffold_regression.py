"""Scaffold pruning must leave a serializable, chemically valid ring/linker graph."""

import unittest
from rdkit import Chem
from tools.implementations.chemistry.rdkit_properties import murcko_decompose


class MurckoScaffoldRegression(unittest.TestCase):
    def test_substituted_aromatic_scaffolds(self):
        fixtures = [
            ("Cc1ccccc1", "c1ccccc1", 6),
            ("COc1ccccc1", "c1ccccc1", 6),
            ("CCc1ccc2ccccc2c1", "c1ccc2ccccc2c1", 10),
            ("c1ccc2ccccc2c1", "c1ccc2ccccc2c1", 10),
            ("CCc1ccc(CCc2ccccc2)cc1", "c1ccc(CCc2ccccc2)cc1", 14),
        ]
        for smiles, expected, count in fixtures:
            with self.subTest(smiles=smiles):
                result = murcko_decompose(smiles)
                canonical = Chem.MolToSmiles(Chem.MolFromSmiles(expected))
                self.assertEqual(result["canonical_smiles"], canonical)
                self.assertEqual(result["atom_count"], count)
                self.assertEqual(len(result["atoms"]), count)
                self.assertIsNotNone(Chem.MolFromSmiles(result["kekule_smiles"]))
                restored = Chem.MolFromMolBlock(result["mol_block"])
                self.assertIsNotNone(restored)
                self.assertEqual(Chem.MolToSmiles(restored), canonical)
                self.assertTrue(all(a["formal_charge"] == 0 for a in result["atoms"]))

    def test_acyclic_structure_has_an_empty_scaffold(self):
        result = murcko_decompose("CCO")
        self.assertEqual(result["canonical_smiles"], "")
        self.assertEqual(result["kekule_smiles"], "")
        self.assertEqual(result["atom_count"], 0)
        self.assertEqual(result["atoms"], [])
        self.assertEqual(result["bonds"], [])

    def test_invalid_structure_is_not_silently_repaired(self):
        with self.assertRaises(ValueError):
            murcko_decompose("c1cccc1")


if __name__ == "__main__":
    unittest.main()
