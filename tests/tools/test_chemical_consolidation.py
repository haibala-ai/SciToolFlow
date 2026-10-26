"""Focused scientific-boundary and consolidation regressions; no network or model tests."""

import ast
import csv
import importlib
import json
from pathlib import Path

import pytest
from tools.catalog import ToolCatalog
from tools.runtime.dispatch import validate_result

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ToolCatalog(ROOT)
SPECS = {
    name: spec for name, spec in CATALOG.tools.items() if spec["domain"] == "Chemical"
}


def call(name, **kwargs):
    spec = SPECS[name]
    fn = getattr(
        importlib.import_module(spec["execution"]["module"]),
        spec["execution"]["function"],
    )
    output = fn(**kwargs)
    validated = validate_result(output, spec)
    assert validated["status"] == "success", (name, validated)
    return output


def test_current_chemical_bindings_and_retirement_targets_are_valid():
    assert SPECS
    assert not set(CATALOG.retired) & set(CATALOG.tools)
    assert all(
        CATALOG.canonical(name) in CATALOG.tools
        for entry in CATALOG.retired.values()
        for name in entry["replacements"]
    )
    for spec in SPECS.values():
        tree = ast.parse((ROOT / spec["source"]["file"]).read_text())
        assert any(
            isinstance(n, ast.FunctionDef) and n.name == spec["source"]["function"]
            for n in tree.body
        ), spec["name"]


def test_wrong_aliphatic_carbocycle_backend_is_corrected():
    assert call("GetAliphaticCarbocyclesNum", smiles="C1CCOC1")["value"] == 0
    assert call("GetAliphaticRingsNum", smiles="C1CCOC1")["value"] == 1
    assert call("GetAliphaticCarbocyclesNum", smiles="C1CCCCC1")["value"] == 1


def test_exact_mass_average_mass_formula_and_donor_acceptor_are_distinct():
    exact = call("GetExactMolceularWeight", smiles="CCO")["value"]
    average = call("SMILESToWeight", smiles="CCO")["molar_mass"]
    assert exact == pytest.approx(46.041864812)
    assert average == pytest.approx(46.069, abs=0.003)
    assert average != pytest.approx(exact, abs=0.001)
    assert call("GetMolFormula", smiles="CCO")["value"] == "C2H6O"
    assert call("GetHBANum", smiles="CC(=O)N(C)C")["value"] == 1
    assert call("GetHBDNum", smiles="CC(=O)N(C)C")["value"] == 0


# A broad set changed from success-shaped Markdown errors to typed finite outputs.
FIXED_DESCRIPTORS = [
    s["name"]
    for s in SPECS.values()
    if s["source"]["file"].endswith(("rdkit_basic.py", "rdkit_properties.py"))
    and any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "descriptor_value"
        for f in ast.parse((ROOT / s["source"]["file"]).read_text()).body
        if isinstance(f, ast.FunctionDef) and f.name == s["source"]["function"]
        for n in ast.walk(f)
    )
]


@pytest.mark.parametrize("name", FIXED_DESCRIPTORS)
def test_fixed_scientific_quantities_return_full_finite_results(name):
    result = call(name, smiles="CC(C)O")
    assert isinstance(result, dict) and "value" in result and result["descriptor"]
    json.dumps(result, allow_nan=False)
    with pytest.raises((ValueError, RuntimeError)):
        call(name, smiles="not a molecular SMILES")


def test_atom_inventory_is_explicit_and_not_inferred_from_atom_count_name():
    assert (
        call("CountMolecularAtoms", source="C", hydrogen_policy="explicit")["count"]
        == 5
    )
    assert call("CountMolecularAtoms", source="[H]C([H])([H])[H]")["count"] == 5
    assert (
        call(
            "CountMolecularAtoms", source="[H]C([H])([H])[H]", hydrogen_policy="remove"
        )["count"]
        == 1
    )
    assert call("CountMolecularAtoms", source="CO", count_kind="heavy")["count"] == 2
    assert call("CountMolecularAtoms", source="CO", count_kind="hetero")["count"] == 1


def _pdb_model(number, shift):
    records = [f"MODEL     {number:4d}\n"]
    for i, (name, element, x, kind) in enumerate(
        [("C1", "C", shift, "ATOM"), ("O1", "O", shift + 3, "HETATM")], 1
    ):
        records.append(
            f"{kind:<6}{i:5d} {name:>4s} LIG A   1    {x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00          {element:>2s}\n"
        )
    return "".join(records) + "ENDMDL\n"


def test_pdb_centroid_preserves_mdanalysis_inventory_models_water_hetero(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SCITOOLFLOW_ARTIFACTS_DIR", str(tmp_path))
    path = tmp_path / "inventory.pdb"
    path.write_text(_pdb_model(1, 0) + _pdb_model(2, 6) + "END\n")
    first = call("MolecularCentroid", source=str(path), source_format="pdb")
    second = call(
        "MolecularCentroid", source=str(path), source_format="pdb", record_index=1
    )
    assert first["centroid"] == [1.5, 0, 0]
    assert second["centroid"] == [7.5, 0, 0]
    assert first["provenance"]["coordinate_unit"] == "angstrom"
    assert (
        call("CountMolecularAtoms", source=str(path), source_format="pdb")["count"] == 2
    )
    with pytest.raises(ValueError):
        call(
            "CountMolecularAtoms",
            source=str(path),
            source_format="pdb",
            count_kind="heavy",
        )


@pytest.mark.parametrize(
    "algorithm",
    [
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
    ],
)
def test_all_explicit_fingerprint_algorithms_are_callable(algorithm):
    result = call("MolecularFingerprint", smiles="CC(C)O", algorithm=algorithm)
    assert result["algorithm"] == algorithm and result["fingerprint"]["length"] > 0
    json.dumps(result, allow_nan=False)


def test_count_presence_and_legacy_path_presets_are_preserved():
    from rdkit import Chem
    from rdkit.Chem.Fingerprints import FingerprintMols

    counts = call("MolecularFingerprint", smiles="CCCC", algorithm="atom_pair")[
        "fingerprint"
    ]["counts"]
    bits = call(
        "MolecularFingerprint",
        smiles="CCCC",
        algorithm="atom_pair",
        options={"representation": "presence"},
    )["fingerprint"]["on_bits"]
    assert sorted(map(int, counts)) == bits
    assert max(counts.values()) > 1
    legacy = {
        "bits": 2048,
        "min_path": 1,
        "max_path": 7,
        "bits_per_hash": 2,
        "use_hs": False,
        "target_density": 0.3,
        "min_size": 64,
    }
    expected = FingerprintMols.FingerprintMol(Chem.MolFromSmiles("CCO"))
    actual = call(
        "MolecularFingerprint", smiles="CCO", algorithm="rdkit", options=legacy
    )["fingerprint"]
    assert actual["length"] == expected.GetNumBits()
    assert actual["on_bits"] == list(expected.GetOnBits())
    with pytest.raises(ValueError, match="Unsupported options"):
        call(
            "MolecularFingerprint",
            smiles="CCO",
            algorithm="rdkit",
            options={"radius": 2},
        )


def test_similarity_one_matrix_order_and_batch_efficiency():
    records = ["CCO", "CCN", "c1ccccc1", "CCC", "CCO"]
    result = call("CompareMolecularFingerprints", smiles_list=records)
    matrix = result["matrix"]
    assert matrix[0][4] == 1
    for i in range(len(records)):
        assert matrix[i][i] == 1
        for j in range(len(records)):
            assert matrix[i][j] == matrix[j][i]
    assert result["operation_counts"] == {
        "records": 5,
        "fingerprint_calculations": 4,
        "symmetric_pair_scores": 15,
    }
    # Compare a non-adjacent 4-record table position to the direct two-record call.
    pair = call("CompareMolecularFingerprints", smiles_list=[records[1], records[3]])
    assert matrix[1][3] == pair["matrix"][0][1]
    distances = call("CompareMolecularFingerprints", smiles_list=records, distance=True)
    assert distances["matrix"][1][3] == 1 - matrix[1][3]


def test_tautomer_aware_and_ordinary_matching_stay_distinct():
    common = dict(
        smiles="CC(=O)C", query="C=C(O)C", query_format="smiles", use_chirality=False
    )
    assert call("SubstructureQuery", **common)["matched"] is False
    assert call("SubstructureQuery", **common, tautomer_aware=True)["matched"] is True
    info = call("InspectTautomerQuery", smiles="CC(=O)C")
    assert len(info["tautomers"]) >= 2 and info["template_fingerprint"]["on_bits"]
    with pytest.raises(ValueError):
        call("SubstructureQuery", smiles="CCO", query="O", tautomer_aware=True)


def test_formal_charge_oxidation_and_pair_distance_are_exposed():
    charges = call("MolecularFormalCharges", smiles="[NH4+].[Cl-]")
    assert charges["total_formal_charge"] == 0
    assert sorted(a["formal_charge"] for a in charges["atoms"]) == [-1, 1]
    oxidation = call("AssignOxidationNumbers", smiles="[Na+].[Cl-]")
    assert sorted(a["oxidation_number"] for a in oxidation["atoms"]) == [-1, 1]
    pair = call("ExplainAtomPairScore", smiles="CCC", atom_idx1=0, atom_idx2=2)
    assert pair["graph_distance"] == 2
    assert pair["decoded"] == [["C", 1, 0], 2, ["C", 1, 0]]
    assert all(isinstance(pair["decoded"][i], list) for i in [0, 2])
    with pytest.raises(ValueError):
        call("ExplainAtomPairScore", smiles="C.C", atom_idx1=0, atom_idx2=1)


def test_geometry_policies_and_supplied_coordinate_bond_perception():
    from rdkit import Chem
    from tools.implementations.chemistry.core import conformer

    values = call("NormalizedPrincipalMoments", smiles="CCO")
    assert 0 <= values["npr1"] <= values["npr2"] <= 1.000001
    with pytest.raises(ValueError, match="connected"):
        call("NormalizedPrincipalMoments", smiles="CCO.[Na+]")
    mol = conformer("CCO")
    rw = Chem.RWMol(mol)
    for bond in list(reversed(list(rw.GetBonds()))):
        rw.RemoveBond(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
    block = Chem.MolToMolBlock(rw)
    result = call("PerceiveBondsFromCoordinates", mol_block=block, charge=0)
    assert len(result["bonds"]) == 8 and result["atom_count"] == 9
    with pytest.raises(ValueError):
        call(
            "PerceiveBondsFromCoordinates", mol_block=block, charge=0, mode="order_only"
        )
    with pytest.raises(ValueError):
        call(
            "AssignChiralTagsFromCoordinates",
            mol_block=Chem.MolToMolBlock(Chem.MolFromSmiles("CCO")),
        )


def test_query_hydrogens_use_returned_query_and_preserve_constraints():
    before = call("InspectQueryHydrogens", smarts="[C]-[H]")
    after = call("MergeQueryHydrogens", smarts="[C]-[H]")
    assert before["has_query_hydrogens"]
    assert after["query_atom_count"] == 1
    assert "H" in after["query_smarts"]


def test_estate_electronic_bundle_and_functional_group_reuse(monkeypatch):
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    values = call("MolecularElectronicDescriptors", smiles="CCO")
    assert values["operation_counts"] == {
        "molecule_parses": 1,
        "estate_calculations": 1,
        "crippen_calculations": 1,
        "gasteiger_assignments": 1,
    }
    reference = Chem.MolFromSmiles("CCO")
    for name, value in values["descriptors"].items():
        assert value == pytest.approx(getattr(Descriptors, name)(reference)), name
    estate = call("EStateAnalysis", smiles="CCO")
    assert values["descriptors"]["MaxEStateIndex"] == max(
        a["estate_index"] for a in estate["atoms"]
    )
    crippen = call(
        "MolecularElectronicDescriptors", smiles="CCO", descriptors=["MolLogP", "MolMR"]
    )["descriptors"]
    assert values["descriptors"]["MolLogP"] == crippen["MolLogP"]
    assert values["descriptors"]["MolMR"] == crippen["MolMR"]
    subset = call(
        "MolecularElectronicDescriptors", smiles="[Na+]", descriptors=["MolLogP"]
    )
    assert subset["operation_counts"]["gasteiger_assignments"] == 0
    groups = call("FuncGroups", smiles="CCO")
    assert groups["operation_counts"]["molecule_parses"] == 1
    alcohol = [g for g in groups["groups"] if g["name"] == "alcohol groups"]
    assert len(alcohol) == 1 and "side-chain hydroxyls" in alcohol[0]["aliases"]
    # FingerprintMol populates the documented EStateIndices(force=False) cache.
    # Retain the backend's type/match rules while avoiding a second O(n^2) pass.
    from rdkit.Chem import EState
    from rdkit.Chem.EState import Fingerprinter

    original_indices = EState.EStateIndices
    operations = {"computations": 0, "cache_hits": 0}

    def tracked_indices(mol, force=True):
        if not force and hasattr(mol, "_eStateIndices"):
            operations["cache_hits"] += 1
        else:
            operations["computations"] += 1
        return original_indices(mol, force=force)

    monkeypatch.setattr(EState, "EStateIndices", tracked_indices)
    monkeypatch.setattr(Fingerprinter, "EStateIndices", tracked_indices)
    actual = call("EStateAnalysis", smiles="CCO")
    assert operations == {"computations": 1, "cache_hits": 1}
    assert actual == estate


def test_streaming_csv_preserves_rows_settings_and_reuses_exact_inputs(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SCITOOLFLOW_ARTIFACTS_DIR", str(tmp_path))
    path = tmp_path / "molecules.csv"
    path.write_text("a,b,label\nCCO,CCN,first\nCCN,CCO,second\nCCO,CCO,third\n")
    result = call(
        "MolecularFingerprint",
        csv_file=str(path),
        columns=["a", "b"],
        options={"radius": 3, "bits": 512},
    )
    assert result["operation_counts"] == {
        "input_cells": 6,
        "unique_molecule_calculations": 2,
    }
    rows = list(csv.DictReader(Path(result["artifact"]).open()))
    assert [r["label"] for r in rows] == ["first", "second", "third"]
    assert [r["source_row_index"] for r in rows] == ["0", "1", "2"]
    assert json.loads(rows[0]["a_fingerprint"])["length"] == 512
    assert result["settings"]["radius"] == 3
    result2 = call(
        "MolecularElectronicDescriptors",
        csv_file=str(path),
        columns=["a"],
        descriptors=["MolLogP", "MolMR"],
    )
    assert result2["operation_counts"]["unique_molecule_calculations"] == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("smiles\nCCO\nnot-a-smiles\n")
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match="data row 1"):
        call("MolecularFingerprint", csv_file=str(bad), columns=["smiles"])
    assert set(tmp_path.iterdir()) == before
    recorded = call(
        "MolecularFingerprint",
        csv_file=str(bad),
        columns=["smiles"],
        invalid_policy="record",
    )
    assert recorded["row_count"] == 2 and recorded["errors"][0]["row_index"] == 1


def test_local_representations_selfies_and_molkey_are_real():
    converted = call("SMILESToInChI", smiles="CCO")
    assert converted["inchi"].startswith("InChI=1S/C2H6O/")
    assert call("InChIToSMILES", inchi=converted["inchi"])["smiles"] == "CCO"
    assert (
        call("InChIToInChIKey", inchi=converted["inchi"])["inchikey"]
        == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    )
    assert call("IsValidInChIKey", inchikey="LFQSCWFLJHTTHZ-UHFFFAOYSA-N")[
        "format_valid"
    ]
    assert not call("IsValidInChIKey", inchikey="not-a-key")["format_valid"]
    info = call("InspectSELFIES", selfies="[C].[O]")
    assert info["tokens"] == ["[C]", ".", "[O]"] and info["symbol_count"] == 3
    first = call("GenerateRandomSELFIES", length=20, seed=42)
    assert first == call("GenerateRandomSELFIES", length=20, seed=42)
    key = call("MolecularKey", smiles="CCO")
    assert key["mol_key"] and key["stereo_code"] and key["error_code"] == 0


def test_catalog_membership_is_not_mislabeled_as_patent_status():
    result = call("QueryMoleculeCatalog", smiles="CCO")
    assert isinstance(result["probably_present"], bool)
    assert result["catalog"] == "zinc-instock-mini"
    assert "false-positive" not in result or "patented" not in result
    assert "not a legal patent" in result["interpretation"]


def test_legacy_duplicate_entrypoints_fail_with_explicit_migration():
    from tools.implementations.chemistry.rdkit_descriptors import (
        build_morgan_fp_from_smiles,
    )

    with pytest.raises(ValueError, match="MolecularFingerprint"):
        build_morgan_fp_from_smiles("CCO")


SINGLE_SMILES = [
    s["name"]
    for s in SPECS.values()
    if s["name"] not in FIXED_DESCRIPTORS
    and s["input_schema"].get("required") == ["smiles"]
]


@pytest.mark.parametrize("name", SINGLE_SMILES)
def test_remaining_single_molecule_contracts_are_typed_and_error_explicit(name):
    result = call(name, smiles="C[C@H](O)CCN")
    assert isinstance(result, dict), name
    json.dumps(result, allow_nan=False)
    with pytest.raises((ValueError, RuntimeError)):
        call(name, smiles="not a molecular SMILES")


def test_getaway_undefined_components_are_explicit_not_zero_imputed():
    result = call("GetGETAWAY", smiles="CC(C)O")
    assert result["undefined_component_indices"] == [
        i for i, x in enumerate(result["value"]) if x is None
    ]
    assert result["status"] in {"complete", "partially_undefined"}
    json.dumps(result, allow_nan=False)


def test_supplied_stereochemistry_coordinates_and_shape_policies():
    from rdkit import Chem
    from tools.implementations.chemistry.core import conformer

    mol = conformer("C[C@H](F)Cl")
    Chem.RemoveStereochemistry(mol)
    block = Chem.MolToMolBlock(mol)
    assigned = call("AssignChiralTagsFromCoordinates", mol_block=block)
    assert any(a["cip_label"] in {"R", "S"} for a in assigned["atoms"])
    result = call("CompareMolecularShapes", source=["CCO", "CCN", "CCO"])
    assert result["similarity_matrix"][0][0] == 1
    assert result["operation_counts"]["generated_conformers"] == 2
    assert result["operation_counts"]["symmetric_pair_scores"] == 6
    assert result["similarity_matrix"][0][2] == 1
    assert call("SlnToSmiles", sln="CH3CH2OH")["smiles"] == "CCO"
    # SLN carbon/hydrogen semantics are not inferred from visually similar SMILES.
    assert call("SlnToSmiles", sln="CCO")["smiles"] == "[C][C][O]"
    assert isinstance(
        call("GetFraggleSimilarity", smiles1="CCO", smiles2="CCN")["similarity"], float
    )


def test_sdf_adapter_coordinate_preservation_and_candidate_dihedrals(
    tmp_path, monkeypatch
):
    from rdkit import Chem
    from tools.implementations.chemistry.core import conformer

    monkeypatch.setenv("SCITOOLFLOW_ARTIFACTS_DIR", str(tmp_path))
    path = tmp_path / "structures.sdf"
    mols = [conformer("CCCC"), conformer("CCCO")]
    writer = Chem.SDWriter(str(path))
    for index, mol in enumerate(mols):
        mol.SetProp("record_label", str(index))
        writer.write(mol)
    writer.close()
    center = call("MolecularCentroid", source=str(path), source_format="sdf")
    expected = mols[0].GetConformer().GetPositions().mean(axis=0)
    assert center["centroid"] == pytest.approx(expected, abs=1e-4)
    comparison = call(
        "CompareMolecularShapes",
        source=str(path),
        source_format="sdf",
        conformer_policy="preserve",
        hydrogen_policy="as_parsed",
    )
    assert comparison["operation_counts"]["generated_conformers"] == 0
    assert comparison["records"][0]["atom_count"] == mols[0].GetNumAtoms()
    converted = call("ConvertSdfToCsv", sdf_file=str(path))
    assert converted["record_count"] == 2
    rows = list(csv.DictReader(Path(converted["artifact"]).open()))
    assert json.loads(rows[0]["properties"])["record_label"] in {"0", 0}
    dihedrals = call("ExtractRotatableDihedralsFromSdf", sdffile=str(path))
    assert dihedrals["candidate_dihedrals"] == [[0, 1, 2, 3]]


def test_additional_inspection_and_clustering_primitives_preserve_their_meanings():
    from rdkit import Chem
    from rdkit.Chem import rdAbbreviations

    assert call("SELFIEStoSMILES", selfies="[C][C][O]")["smiles"] == "CCO"
    capabilities = call("RDKitCapabilities")
    assert (
        capabilities["rdkit_version"]
        and type(capabilities["tautomer_query_serializable"]) is bool
    )
    codes = call(
        "AtomPairCodes", smiles="CCC", atom_indices=[0, 2], include_chirality=False
    )
    assert [a["atom_index"] for a in codes["atoms"]] == [0, 2]
    assert codes["atoms"][0]["code"] == codes["atoms"][1]["code"]
    for method in ["butina", "average"]:
        clusters = call(
            "ClusterMolecularFingerprints",
            smiles_list=["CCO", "CCCCCCCC", "CCO"],
            threshold=0.05,
            method=method,
        )["clusters"]
        assert any(0 in cluster and 2 in cluster for cluster in clusters)
        assert sorted(i for cluster in clusters for i in cluster) == [0, 1, 2]
    mol = Chem.MolFromSmiles("CC=CC")
    mol.GetBondWithIdx(1).SetStereo(Chem.BondStereo.STEREOANY)
    wavy = call("AddWavyStereoBonds", mol_block=Chem.MolToMolBlock(mol))
    assert any(b["direction"] == "UNKNOWN" for b in wavy["bonds"])
    original = Chem.MolFromSmiles("CC(C)(C)c1ccccc1")
    labeled = rdAbbreviations.LabelMolAbbreviations(
        original, rdAbbreviations.GetDefaultAbbreviations(), maxCoverage=1
    )
    # V3000 preserves attachment identifiers accepted by this RDKit parser.
    condensed = call(
        "CondenseAbbreviations", mol_block=Chem.MolToMolBlock(labeled, forceV3000=True)
    )
    assert condensed["atom_count"] < original.GetNumAtoms()
