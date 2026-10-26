"""Real local inline/CSV parity and transport contracts; no remote services."""

import copy
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from tools.catalog import ToolCatalog
from tools.runtime.dispatch import validate_result as public_validate_result

from tools.implementations.chemistry.fingerprints import (
    molecular_fingerprint,
    fingerprint_csv,
)
from tools.implementations.chemistry.electronic_descriptors import (
    electronic_descriptors,
    electronic_descriptors_csv,
)


ROOT = Path(__file__).resolve().parents[2]


class MolecularTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = ToolCatalog(ROOT)
        cls.specs = {
            name: cls.catalog.tools[name]
            for name in ("MolecularFingerprint", "MolecularElectronicDescriptors")
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": str(self.directory)}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.source = self.directory / "molecules.csv"
        self.source.write_text(
            "smiles,other,label\nCCO,CCN,first\nCCN,CCO,second\nCCO,CCO,third\n"
        )

    def validate_result(self, name, value):
        schema = self.specs[name]["output_schema"]
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
        checked = public_validate_result(value, self.specs[name])
        self.assertEqual(checked["status"], "success", checked)
        json.dumps(value, allow_nan=False)

    def test_fingerprint_inline_csv_values_settings_rows_and_cache_are_identical(self):
        options = {"radius": 3, "bits": 512, "chirality": True}
        inline = molecular_fingerprint("CCO", options=options)
        file_result = molecular_fingerprint(
            csv_file=str(self.source), columns=["smiles", "other"], options=options
        )
        self.assertEqual(inline["input_mode"], "inline")
        self.assertEqual(file_result["input_mode"], "csv")
        self.assertEqual(inline["settings"], file_result["settings"])
        self.assertEqual(
            file_result["operation_counts"],
            {"input_cells": 6, "unique_molecule_calculations": 2},
        )
        with Path(file_result["artifact"]).open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([r["source_row_index"] for r in rows], ["0", "1", "2"])
        self.assertEqual([r["label"] for r in rows], ["first", "second", "third"])
        self.assertEqual(
            json.loads(rows[0]["smiles_fingerprint"]), inline["fingerprint"]
        )
        self.assertEqual(
            json.loads(rows[1]["other_fingerprint"]), inline["fingerprint"]
        )
        self.assertEqual(file_result["source"], str(self.source))
        self.assertEqual(len(file_result["source_sha256"]), 64)
        self.assertEqual(len(file_result["output_sha256"]), 64)
        self.validate_result("MolecularFingerprint", inline)
        self.validate_result("MolecularFingerprint", file_result)

    def test_electronic_values_match_inline_and_schema_is_disjoint(self):
        names = ["MolLogP", "MolMR", "MaxPartialCharge", "MinAbsPartialCharge"]
        inline = electronic_descriptors("CCO", descriptors=names)
        file_result = electronic_descriptors(
            csv_file=str(self.source), columns=["smiles"], descriptors=names
        )
        with Path(file_result["artifact"]).open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(
            json.loads(rows[0]["smiles_electronic_descriptors"]), inline["descriptors"]
        )
        self.assertEqual(file_result["descriptor_names"], names)
        self.assertEqual(
            file_result["operation_counts"],
            {"input_cells": 3, "unique_molecule_calculations": 2},
        )
        self.validate_result("MolecularElectronicDescriptors", inline)
        self.validate_result("MolecularElectronicDescriptors", file_result)
        mixed = copy.deepcopy(inline)
        mixed["artifact"] = file_result["artifact"]
        self.assertTrue(
            list(
                Draft202012Validator(
                    self.specs["MolecularElectronicDescriptors"]["output_schema"]
                ).iter_errors(mixed)
            )
        )

    def test_input_modes_are_exclusive_before_file_access_or_scientific_work(self):
        for fn in (molecular_fingerprint, electronic_descriptors):
            with (
                self.subTest(fn=fn.__name__),
                patch("tools.implementations.chemistry.core.source_bytes") as source,
            ):
                for kwargs in ({}, {"smiles": "CCO", "csv_file": str(self.source)}):
                    with self.assertRaisesRegex(ValueError, "exactly one"):
                        fn(**kwargs)
                for kwargs in (
                    {"smiles": "CCO", "columns": ["smiles"]},
                    {"smiles": "CCO", "invalid_policy": "record"},
                ):
                    with self.assertRaisesRegex(ValueError, "only to csv_file"):
                        fn(**kwargs)
                source.assert_not_called()
                with self.assertRaisesRegex(ValueError, "columns must contain"):
                    fn(csv_file=str(self.source))
                source.assert_not_called()

    def test_invalid_csv_cells_have_explicit_policy_and_partial_artifact_cleanup(self):
        self.source.write_text(
            "smiles,label\nCCO,valid\ninvalid-smiles,invalid\nCCO,repeat\n"
        )
        for name, fn, suffix in (
            ("MolecularFingerprint", molecular_fingerprint, "_fingerprint"),
            (
                "MolecularElectronicDescriptors",
                electronic_descriptors,
                "_electronic_descriptors",
            ),
        ):
            with self.subTest(tool=name):
                before = set(self.directory.iterdir())
                with self.assertRaisesRegex(ValueError, "data row 1, column smiles"):
                    fn(csv_file=str(self.source), columns=["smiles"])
                self.assertEqual(set(self.directory.iterdir()), before)
                recorded = fn(
                    csv_file=str(self.source),
                    columns=["smiles"],
                    invalid_policy="record",
                )
                self.assertEqual(recorded["errors"][0]["row_index"], 1)
                self.assertEqual(recorded["errors"][0]["column"], "smiles")
                self.assertEqual(recorded["row_count"], 3)
                self.assertEqual(
                    recorded["operation_counts"]["unique_molecule_calculations"], 2
                )
                with Path(recorded["artifact"]).open() as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(rows[1]["smiles" + suffix], "null")
                self.assertEqual(
                    [r["label"] for r in rows], ["valid", "invalid", "repeat"]
                )
                self.validate_result(name, recorded)

    def test_input_schemas_match_both_modes_and_reject_mixed_or_missing_source(self):
        for name in self.specs:
            validator = Draft202012Validator(self.specs[name]["input_schema"])
            Draft202012Validator.check_schema(validator.schema)
            for kwargs in (
                {"smiles": "CCO"},
                {"smiles": "CCO", "csv_file": None, "columns": None},
                {"csv_file": str(self.source), "columns": ["smiles"]},
                {
                    "smiles": None,
                    "csv_file": str(self.source),
                    "columns": ["smiles"],
                    "invalid_policy": "record",
                },
            ):
                self.assertFalse(list(validator.iter_errors(kwargs)), (name, kwargs))
            for kwargs in (
                {},
                {"smiles": None},
                {"csv_file": str(self.source)},
                {"smiles": "CCO", "csv_file": str(self.source), "columns": ["smiles"]},
                {"smiles": "CCO", "invalid_policy": "record"},
            ):
                self.assertTrue(list(validator.iter_errors(kwargs)), (name, kwargs))

    def test_transport_only_legacy_functions_fail_with_canonical_migration(self):
        for fn, canonical in (
            (fingerprint_csv, "MolecularFingerprint"),
            (electronic_descriptors_csv, "MolecularElectronicDescriptors"),
        ):
            with self.assertRaisesRegex(NotImplementedError, canonical):
                fn(str(self.source), ["smiles"])

    def test_crippen_pair_subset_has_one_canonical_with_unchanged_backend_values(self):
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors
        from tools.implementations.chemistry.rdkit_basic import (
            calculate_crippen_descriptors,
        )

        with self.assertRaisesRegex(
            NotImplementedError, "MolecularElectronicDescriptors"
        ):
            calculate_crippen_descriptors("CCO")
        # Named result replaces the old positional pair, using the exact backend.
        expected = rdMolDescriptors.CalcCrippenDescriptors(Chem.MolFromSmiles("CCO"))
        actual = electronic_descriptors("CCO", descriptors=["MolLogP", "MolMR"])
        self.assertEqual(
            actual["descriptors"], dict(zip(["MolLogP", "MolMR"], expected))
        )
        self.assertEqual(actual["hydrogen_policy"], "remove")
        self.assertEqual(actual["operation_counts"]["crippen_calculations"], 1)
        self.assertEqual(actual["operation_counts"]["estate_calculations"], 0)
        self.assertEqual(actual["operation_counts"]["gasteiger_assignments"], 0)
        self.validate_result("MolecularElectronicDescriptors", actual)

    def test_every_electronic_singleton_pair_and_default_mode_validates_current_public_schema(
        self,
    ):
        from tools.implementations.chemistry.electronic_descriptors import NAMES

        selections = [[name] for name in NAMES] + [["MolLogP", "MolMR"], None]
        estate = {"MaxEStateIndex", "MinAbsEStateIndex", "MinEStateIndex"}
        crippen = {"MolLogP", "MolMR"}
        charges = {
            "MaxPartialCharge",
            "MinPartialCharge",
            "MaxAbsPartialCharge",
            "MinAbsPartialCharge",
        }
        leaf_schema = self.specs["MolecularElectronicDescriptors"]["output_schema"][
            "properties"
        ]["descriptors"]
        for selection in selections:
            with self.subTest(selection=selection):
                selected = set(NAMES if selection is None else selection)
                value = electronic_descriptors("CCO", descriptors=selection)
                expected_counts = {
                    "molecule_parses": 1,
                    "estate_calculations": int(bool(selected & estate)),
                    "crippen_calculations": int(bool(selected & crippen)),
                    "gasteiger_assignments": int(bool(selected & charges)),
                }
                self.assertEqual(set(value["descriptors"]), selected)
                self.assertEqual(value["operation_counts"], expected_counts)
                self.assertEqual(
                    value["gasteiger_iterations"], 12 if selected & charges else None
                )
                self.validate_result("MolecularElectronicDescriptors", value)
                file_value = electronic_descriptors(
                    csv_file=str(self.source), columns=["smiles"], descriptors=selection
                )
                self.validate_result("MolecularElectronicDescriptors", file_value)
                self.assertEqual(
                    file_value["descriptor_names"],
                    NAMES if selection is None else selection,
                )
                self.assertEqual(
                    file_value["operation_counts"],
                    {"input_cells": 3, "unique_molecule_calculations": 2},
                )
                with Path(file_value["artifact"]).open() as stream:
                    rows = list(csv.DictReader(stream))
                decoded = json.loads(rows[0]["smiles_electronic_descriptors"])
                Draft202012Validator(leaf_schema).validate(decoded)
                self.assertEqual(decoded, value["descriptors"])

    def test_electronic_schema_rejects_wrong_null_or_unrequested_dependency_metadata(
        self,
    ):
        for selected in (
            ["MolLogP", "MolMR"],
            ["MaxPartialCharge"],
            ["MaxEStateIndex"],
            ["qed"],
        ):
            value = electronic_descriptors("CCO", descriptors=selected)
            self.validate_result("MolecularElectronicDescriptors", value)
            wrong = copy.deepcopy(value)
            wrong["gasteiger_iterations"] = (
                None if value["gasteiger_iterations"] == 12 else 12
            )
            self.assertEqual(
                public_validate_result(
                    wrong, self.specs["MolecularElectronicDescriptors"]
                )["error_type"],
                "InvalidOutput",
            )
            for counter in (
                "estate_calculations",
                "crippen_calculations",
                "gasteiger_assignments",
            ):
                wrong = copy.deepcopy(value)
                wrong["operation_counts"][counter] = (
                    1 - wrong["operation_counts"][counter]
                )
                self.assertEqual(
                    public_validate_result(
                        wrong, self.specs["MolecularElectronicDescriptors"]
                    )["error_type"],
                    "InvalidOutput",
                )

    def test_all_ten_fingerprint_algorithms_and_representation_modes_validate_current_public_schema(
        self,
    ):
        algorithms = [
            "morgan",
            "rdkit",
            "atom_pair",
            "torsion",
            "maccs",
            "avalon",
            "pharm2d",
            "mhfp",
            "secfp",
            "tautomer_target",
        ]
        cases = [(algorithm, None) for algorithm in algorithms] + [
            ("atom_pair", {"representation": "presence"}),
            ("morgan", {"bits": 64, "radius": 3, "chirality": True}),
            (
                "rdkit",
                {
                    "bits": 2048,
                    "min_path": 1,
                    "max_path": 7,
                    "bits_per_hash": 2,
                    "use_hs": False,
                    "target_density": 0.3,
                    "min_size": 64,
                },
            ),
        ]
        payload_schema = self.specs["MolecularFingerprint"]["output_schema"][
            "properties"
        ]["fingerprint"]
        for algorithm, options in cases:
            with self.subTest(algorithm=algorithm, options=options):
                value = molecular_fingerprint(
                    "CCO", algorithm=algorithm, options=options
                )
                self.validate_result("MolecularFingerprint", value)
                file_value = molecular_fingerprint(
                    csv_file=str(self.source),
                    columns=["smiles"],
                    algorithm=algorithm,
                    options=options,
                )
                self.validate_result("MolecularFingerprint", file_value)
                self.assertEqual(file_value["settings"], value["settings"])
                self.assertEqual(
                    file_value["operation_counts"],
                    {"input_cells": 3, "unique_molecule_calculations": 2},
                )
                with Path(file_value["artifact"]).open() as stream:
                    first = next(csv.DictReader(stream))
                encoded_payload = json.loads(first["smiles_fingerprint"])
                Draft202012Validator(payload_schema).validate(encoded_payload)
                self.assertEqual(encoded_payload, value["fingerprint"])
                payload = value["fingerprint"]
                if algorithm == "mhfp":
                    self.assertEqual(
                        set(payload), {"representation", "values", "length"}
                    )
                    self.assertEqual(payload["representation"], "minhash")
                    self.assertEqual(
                        len(payload["values"]), value["settings"]["permutations"]
                    )
                    self.assertEqual(payload["length"], len(payload["values"]))
                elif algorithm == "torsion" or (
                    algorithm == "atom_pair"
                    and value["settings"]["representation"] == "counts"
                ):
                    self.assertEqual(
                        set(payload), {"representation", "counts", "length"}
                    )
                    self.assertEqual(payload["representation"], "sparse_counts")
                    self.assertTrue(
                        all(
                            0 <= int(i) < payload["length"] and count > 0
                            for i, count in payload["counts"].items()
                        )
                    )
                else:
                    self.assertEqual(
                        set(payload), {"representation", "on_bits", "length"}
                    )
                    self.assertEqual(payload["representation"], "bits")
                    self.assertTrue(
                        all(0 <= i < payload["length"] for i in payload["on_bits"])
                    )
                    if "bits" in value["settings"]:
                        if algorithm == "rdkit" and value["settings"]["target_density"]:
                            self.assertLessEqual(
                                value["settings"]["min_size"], payload["length"]
                            )
                            self.assertLessEqual(
                                payload["length"], value["settings"]["bits"]
                            )
                        else:
                            self.assertEqual(
                                payload["length"], value["settings"]["bits"]
                            )
                    if algorithm == "maccs":
                        self.assertEqual(payload["length"], 167)

    def test_fingerprint_schema_rejects_cross_method_settings_and_mixed_representations(
        self,
    ):
        value = molecular_fingerprint("CCO", algorithm="maccs")
        self.validate_result("MolecularFingerprint", value)
        wrong = copy.deepcopy(value)
        wrong["settings"]["radius"] = 2
        self.assertEqual(
            public_validate_result(wrong, self.specs["MolecularFingerprint"])[
                "error_type"
            ],
            "InvalidOutput",
        )
        wrong = copy.deepcopy(value)
        wrong["fingerprint"]["counts"] = {"1": 1}
        self.assertEqual(
            public_validate_result(wrong, self.specs["MolecularFingerprint"])[
                "error_type"
            ],
            "InvalidOutput",
        )

    def test_every_retired_csv_reference_points_directly_to_an_active_canonical(self):
        all_retirements = self.catalog.retired
        for name, entry in all_retirements.items():
            self.assertNotIn("FingerprintCSV", entry["replacements"], name)
            self.assertNotIn("ElectronicDescriptorsCSV", entry["replacements"], name)
        self.assertEqual(
            all_retirements["GenerateMorganfingerprintsFromCSV"]["argument_migration"][
                "options"
            ],
            {"radius": 3, "bits": 512},
        )
        self.assertEqual(
            all_retirements["FingerprintsFromSmiles"]["argument_migration"][
                "legacy_options"
            ]["target_density"],
            0.3,
        )


if __name__ == "__main__":
    unittest.main()
