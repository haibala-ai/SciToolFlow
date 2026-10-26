"""Scientific representation regressions discovered during task redesign."""

import ast
import re
import unittest


class ChemicalInputIntegrityTests(unittest.TestCase):
    def test_salt_components_are_not_joined_by_smiles_cleaning(self):
        from tools.implementations.chemistry.rdkit_properties import get_molfrags

        output = get_molfrags("CC(=O)[O-].[Na+]")
        self.assertIn("CC(=O)[O-].[Na+]", output)
        fragments = ast.literal_eval(output.split("**Mol Frags:**", 1)[1].strip())
        self.assertEqual(len(fragments), 2)
        self.assertEqual(sorted(map(len, fragments)), [1, 4])

    def groups(self, smiles):
        from tools.implementations.chemistry.rxn4chem_ncbi import list_functional_groups

        output = list_functional_groups(smiles)
        return {group["name"] for group in output["groups"]}

    def test_ester_does_not_imply_ketone_or_aldehyde(self):
        groups = self.groups("CCOC(=O)C")
        self.assertIn("esters", groups)
        self.assertIn("carbonyl groups", groups)
        self.assertNotIn("ketones", groups)
        self.assertNotIn("terminal aldehyde", groups)
        self.assertNotIn("carboxylic acids", groups)

    def test_free_acid_and_alcohol_are_distinct_patterns(self):
        acid = self.groups("CC(=O)O")
        alcohol = self.groups("CCO")
        self.assertIn("carboxylic acids", acid)
        self.assertNotIn("alcohol groups", acid)
        self.assertIn("alcohol groups", alcohol)
        self.assertNotIn("carboxylic acids", alcohol)

    def test_amide_nitrogen_is_not_primary_amine(self):
        groups = self.groups("CC(=O)N")
        self.assertIn("amides", groups)
        self.assertNotIn("primary amines", groups)


if __name__ == "__main__":
    unittest.main()
