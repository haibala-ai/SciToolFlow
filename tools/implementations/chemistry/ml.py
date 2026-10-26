"""Retired CSV model adapters; use the explicit current catalog contracts.

Legacy filename inference, implicit label binning and zero imputation are removed.
These names are not public tools. They remain only to give direct old imports a
clear migration error; no scientific result is computed here.
"""

def Generate_ElectricalDescriptors_from_csv(csv_name: str):
    """Retired entry: query DescribeTools for MolecularElectronicDescriptors."""
    raise ValueError("Retired CSV adapter. Use MolecularElectronicDescriptors with explicit csv_file and columns, with smiles omitted; no implicit filename, label or feature migration is available.")


def Generate_Morganfingerprints_from_csv(csv_name: str):
    """Retired entry: query DescribeTools for MolecularFingerprint."""
    raise ValueError("Retired CSV adapter. Use MolecularFingerprint with explicit csv_file and columns, algorithm=morgan and options radius=3/bits=512, with smiles omitted; no implicit filename, label or feature migration is available.")


def Generate_RDKfingerprints_from_csv(csv_name: str):
    """Retired entry: query DescribeTools for MolecularFingerprint."""
    raise ValueError("Retired CSV adapter. Use MolecularFingerprint with explicit csv_file and columns, algorithm=rdkit and options bits=512, with smiles omitted; no implicit filename, label or feature migration is available.")


def MLP_Classifier(csv_name: str):
    """Retired entry: query DescribeTools for TrainAndPredictClassifier."""
    raise ValueError("Retired CSV adapter. Use TrainAndPredictClassifier with its explicit current input contract; no implicit filename, label or feature migration is available.")


def AdaBoost_Classifier(csv_name: str):
    """Retired entry: query DescribeTools for TrainAndPredictClassifier."""
    raise ValueError("Retired CSV adapter. Use TrainAndPredictClassifier with its explicit current input contract; no implicit filename, label or feature migration is available.")


def RandomForest_Classifier(csv_name: str):
    """Retired entry: query DescribeTools for TrainAndPredictClassifier."""
    raise ValueError("Retired CSV adapter. Use TrainAndPredictClassifier with its explicit current input contract; no implicit filename, label or feature migration is available.")


