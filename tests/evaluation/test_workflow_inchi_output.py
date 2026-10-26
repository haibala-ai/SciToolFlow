import pytest
from evaluation.workflow import MissingEvidence, operand, validate_workflow

INCHI = "InChI=1S/CH4/h1H4"


def extract(value):
    return operand({"operation": "inchi_identifier", "args": [{"value": value}]}, {})


@pytest.mark.parametrize(
    "value",
    [
        INCHI,
        "\n" + INCHI + "\n",
        "\n**SMILES to InChI**\nSMILES=C\n**Result:**\n" + INCHI + "\n",
        "### SMILES to InChI Conversion\n\n- SMILES: `C`\n- InChI: `" + INCHI + "`\n",
    ],
)
def test_observed_inchi_contracts(value):
    assert extract(value) == INCHI


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        {},
        "",
        "SMILES=" + INCHI,
        "### SMILES to InChI Conversion\n- SMILES: `" + INCHI + "`\n",
        "### SMILES to InChI Conversion\n- InChI: `"
        + INCHI
        + "`\n- InChI: `"
        + INCHI
        + "`",
        "**SMILES to InChI**\n**Result:**\n" + INCHI + "\nextra text",
        "**SMILES to InChI**\n**Result:**\n" + INCHI + "\n**Result:**\n" + INCHI,
        INCHI + "\n" + INCHI,
        "InChI=1S/CH4/\x00",
        "InChI=1S/",
    ],
)
def test_incomplete_ambiguous_or_echo_only_output_is_not_evidence(value):
    with pytest.raises(MissingEvidence):
        extract(value)


def test_inchi_operation_is_registered_in_the_production_spec_validator():
    validate_workflow(
        {
            "schema_version": "workflow.v1",
            "nodes": [
                {
                    "id": "identity",
                    "alternatives": [
                        {
                            "tools": ["ConvertSmilesToInchi"],
                            "output_rules": [
                                {
                                    "left": {
                                        "operation": "inchi_identifier",
                                        "args": [{"source": "call_output", "path": ""}],
                                    },
                                    "op": "eq",
                                    "value": INCHI,
                                }
                            ],
                        }
                    ],
                }
            ],
            "outcomes": [
                {
                    "id": "answer",
                    "left": {"source": "answer", "path": "/inchi"},
                    "op": "eq",
                    "value": INCHI,
                    "evidence_nodes": ["identity"],
                }
            ],
        }
    )
