"""Run the author's public MOFSimplify models with real RAC/Zeo++ features."""

from src.utils.paths import local_root, artifacts_root
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import uuid

ROOT = local_root()


def _number(line, label):
    match = re.search(re.escape(label) + r"\s*([-+\deE.]+)", line)
    if not match:
        raise RuntimeError("Missing Zeo++ output label: " + label)
    return float(match.group(1))


def _geometry(cif, directory):
    import numpy as np

    executable = Path(
        os.getenv(
            "SCITOOL_ZEOPP_EXECUTABLE",
            str(ROOT / "external_sources/zeopp-lsmo/zeo++/network"),
        )
    )
    commands = {
        "pd": ["-ha", "-res"],
        "sa": ["-sa", "1.86", "1.86", "10000"],
        "pov": ["-volpo", "1.86", "1.86", "10000"],
    }
    paths = {}
    for label, arguments in commands.items():
        path = directory / (label + ".txt")
        response = subprocess.run(
            [str(executable), *arguments, str(path), str(cif)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        (directory / (label + ".log")).write_text(response.stdout + response.stderr)
        response.check_returncode()
        if not path.is_file():
            raise RuntimeError("Zeo++ did not produce " + label)
        paths[label] = path
    pd = paths["pd"].read_text().splitlines()[0].split()
    sa = paths["sa"].read_text().splitlines()[0]
    pov = paths["pov"].read_text().splitlines()[0]
    density = _number(pov, "Density:")
    fraction = _number(pov, "POAV_Volume_fraction:") + _number(
        pov, "PONAV_Volume_fraction:"
    )
    features = {
        "Di": float(pd[1]),
        "Df": float(pd[2]),
        "Dif": float(pd[3]),
        "cell_v": _number(sa, "Unitcell_volume:"),
        "VSA": _number(sa, "ASA_m^2/cm^3:"),
        "GSA": _number(sa, "ASA_m^2/g:"),
        "VPOV": fraction,
        "GPOV": fraction / density,
        "POAV_vol_frac": _number(pov, "POAV_Volume_fraction:"),
        "PONAV_vol_frac": _number(pov, "PONAV_Volume_fraction:"),
        "GPOAV": _number(pov, "POAV_cm^3/g:"),
        "GPONAV": _number(pov, "PONAV_cm^3/g:"),
        "POAV": _number(pov, "POAV_A^3:"),
        "PONAV": _number(pov, "PONAV_A^3:"),
    }
    if not all(np.isfinite(value) for value in features.values()):
        raise RuntimeError("Non-finite Zeo++ descriptors")
    return features


def predict_stability(cif_file_name: str):
    """Predict thermal decomposition temperature (Celsius) and solvent-removal stability with configured MOFSimplify weights.

    Returns a JSON string with the actual input CIF source_sha256, model
    estimates and retained artifact path. These are computational model
    predictions, not measured operating limits. A source changed during the
    calculation raises an explicit error.
    """
    if not isinstance(cif_file_name, str) or not cif_file_name.strip():
        raise ValueError("cif_file_name must be an explicit CIF attachment name/path")
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "4")
    os.environ.setdefault("TF_NUM_INTEROP_THREADS", "2")
    import numpy as np
    import pandas as pd
    import io
    from importlib.metadata import version
    from tensorflow import keras
    from sklearn.preprocessing import StandardScaler
    from tools.runtime.config import Config
    from tools.implementations.materials.support.mof_descriptors import (
        get_primitive,
        get_MOF_descriptors,
    )
    from tools.implementations.materials.support.mof_func import RACs, geo

    filename = (
        cif_file_name if cif_file_name.endswith(".cif") else cif_file_name + ".cif"
    )
    cif = Path(Config().UPLOAD_FILES_BASE_PATH) / filename
    if not cif.is_file():
        raise FileNotFoundError(str(cif))
    source_sha256 = hashlib.sha256(cif.read_bytes()).hexdigest()
    geometry_executable = Path(os.getenv("SCITOOL_ZEOPP_EXECUTABLE",
        str(ROOT / "external_sources/zeopp-lsmo/zeo++/network")))
    geometry_sha256 = hashlib.sha256(geometry_executable.read_bytes()).hexdigest()
    directory = artifacts_root() / ("mof_stability_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    primitive = directory / "primitive.cif"
    get_primitive(str(cif), str(primitive))
    names, values = get_MOF_descriptors(
        str(primitive),
        3,
        path=str(directory) + "/",
        xyzpath=str(directory / "primitive.xyz"),
    )
    if len(names) != len(values) or len(names) < 20:
        raise RuntimeError("MOF RAC featurization failed")
    features = dict(zip(names, values))
    features.update(_geometry(primitive, directory))
    if hashlib.sha256(geometry_executable.read_bytes()).hexdigest() != geometry_sha256:
        raise RuntimeError("Zeo++ executable changed during feature calculation")
    base = (
        Path(Config().SOLVENT_THERMAL_MODEL_PATH or str(ROOT / "models/MOFSimplify"))
        / "model"
    )
    results = {}
    contracts = {}
    for kind, label, model_name in [
        ("thermal", "T", "final_model_T_few_epochs.h5"),
        ("solvent", "flag", "final_model_flag_few_epochs.h5"),
    ]:
        training = (
            base
            / kind
            / "ANN"
            / (
                "dropped_connectivity_dupes/train.csv"
                if kind == "solvent"
                else "train.csv"
            )
        )
        training_bytes = training.read_bytes()
        training_sha256 = hashlib.sha256(training_bytes).hexdigest()
        frame = pd.read_csv(io.BytesIO(training_bytes))
        frame = frame.loc[:, (frame != frame.iloc[0]).any()]
        author_geo = ["cell_v" if name == "rho" else name for name in geo]
        columns = [column for column in frame.columns if column in RACs + author_geo]
        valid = frame.dropna(subset=columns + [label])
        missing = [column for column in columns if column not in features]
        if missing:
            raise RuntimeError("Missing MOF descriptors: " + ",".join(missing))
        scaler = StandardScaler().fit(valid[columns].values)
        vector = np.array([[features[column] for column in columns]], dtype=float)
        if not np.isfinite(vector).all():
            raise RuntimeError("Non-finite MOF feature vector")
        model_file = base / kind / "ANN" / model_name
        model_sha256 = hashlib.sha256(model_file.read_bytes()).hexdigest()
        model = keras.models.load_model(model_file, compile=False)
        if hashlib.sha256(model_file.read_bytes()).hexdigest() != model_sha256:
            raise RuntimeError("Configured MOFSimplify model changed while loading")
        if model.input_shape[-1] != len(columns):
            raise RuntimeError(
                f"MOF {kind} feature dimension mismatch: model {model.input_shape[-1]}, table {len(columns)}"
            )
        output = np.asarray(model(scaler.transform(vector), training=False))
        if kind == "thermal":
            output = (
                StandardScaler().fit(valid[[label]].values).inverse_transform(output)
            )
        value = float(output.reshape(-1)[0])
        if not np.isfinite(value) or kind == "solvent" and not 0 <= value <= 1:
            raise RuntimeError("Invalid MOF model output")
        results[kind] = value
        contracts[kind] = {
            "model": str(base / kind / "ANN" / model_name),
            "model_sha256": model_sha256,
            "training_table": str(training),
            "training_table_sha256": training_sha256,
            "feature_columns": columns,
            "training_rows": len(valid),
        }
    artifact = directory / "prediction.json"
    report = {
        "source": "hjkgrp/MOFSimplify method with explicitly configured model/training artifacts",
        "input_cif": str(cif),
        "source_sha256": source_sha256,
        "thermal_decomposition_temperature_celsius": results["thermal"],
        "solvent_removal_stability_probability": results["solvent"],
        "feature_note": "The author's cell_v feature is cell volume in angstrom^3; earlier code called it rho, as corrected in the author README.",
        "geometric_samples": 10000,
        "features": features,
        "contracts": contracts,
        "model_artifacts": {kind: {key: value for key, value in contract.items()
                                    if key in ["model_sha256", "training_table_sha256"]}
                            for kind, contract in contracts.items()},
        "feature_software": {"zeopp_executable_sha256": geometry_sha256,
                             "pymatgen_version": version("pymatgen"),
                             "molsimplify_version": version("molSimplify")},
    }
    if hashlib.sha256(cif.read_bytes()).hexdigest() != source_sha256:
        raise RuntimeError("Input CIF changed during the stability calculation")
    artifact.write_text(json.dumps(report, indent=2, default=float))
    return json.dumps(
        {
            key: value
            for key, value in report.items()
            if key not in ["features", "contracts"]
        }
        | {"artifact": str(artifact)}
    )
