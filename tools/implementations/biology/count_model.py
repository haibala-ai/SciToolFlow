"""Bounded, file-based PyDESeq2 fitting of an entire supplied count universe.

This module does not choose genes, adjust p-values, shrink fold changes, or make
biological claims. Large results are task-local artifacts for downstream tools.
"""

import contextlib
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import time
import uuid
import warnings
from pathlib import Path


def _table(path, delimiter):
    raw = path.read_bytes()
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("Each input file is limited to 50 MiB")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=delimiter))
    if len(rows) < 2 or not rows[0] or any(not field for field in rows[0]):
        raise ValueError("Input needs a nonempty header and at least one data row")
    if len(set(rows[0])) != len(rows[0]):
        raise ValueError("Duplicate input header fields")
    if any(len(row) != len(rows[0]) for row in rows[1:]):
        raise ValueError("Input has inconsistent row widths or blank rows")
    return rows[0], rows[1:], hashlib.sha256(raw).hexdigest()


def _finite(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def fit_bulk_rnaseq_counts(
    counts_file: str,
    metadata_file: str,
    design_factors: list[str],
    contrast: list[str],
    sample_id_column: str = "sample_id",
    gene_id_column: str = "gene_id",
    metadata_id_suffix: str = "",
    sample_subset: list[str] | None = None,
    fit_type: str = "parametric",
    cooks_filter: bool = True,
    use_cache: bool = True,
) -> dict:
    """Fit an additive categorical bulk RNA-seq negative-binomial count model.

    Args:
        counts_file: Uploaded UTF-8 TSV: one row per gene, an explicit gene ID
            column, and otherwise only sample columns with raw integer counts.
        metadata_file: Uploaded UTF-8 CSV, one row per sample. No extra or missing
            samples are accepted, even if a sample subset is subsequently chosen.
        design_factors: Unique categorical metadata column names for an additive
            intercept-plus-factors design. Continuous covariates/interactions are
            not supported. Order has no scientific meaning and is canonicalized
            lexically before coding/fitting/cache identity. Full rank and at
            least two residual df are required.
        contrast: Exactly [factor, tested_level, reference_level]; signed log2FC
            is tested/reference. Both levels need at least two fitted samples.
        sample_id_column: Metadata identity column, not a design factor.
        gene_id_column: Count-table identity column; all other columns are counts.
        metadata_id_suffix: If nonempty, require and remove exactly this suffix
            from EVERY metadata sample ID before matching the count columns.
        sample_subset: Optional unique exact count sample IDs. No gene subset is
            supported: ALL provided genes form the model's input universe.
        fit_type: PyDESeq2 dispersion trend request, 'parametric' or 'mean'. The
            actual library fallback and warnings are returned separately.
        cooks_filter: Apply library Cook's-distance p-value filtering. No count
            replacement is performed, regardless of this setting.
        use_cache: Reuse a content-, parameter-, version-, and source-keyed CPU
            result. Every call writes a fresh task-local output artifact.

    Returns:
        A compact result with result file path/SHA, method and universe metadata,
        fit diagnostics, and at most five gene rows as a preview. The full JSON
        file has data (ALL input genes) and model. Each gene row has gene_id,
        base_mean, log2_fold_change, log2_standard_error, wald_statistic, p_value,
        lfc_converged, testable and test_status. Nonfinite or untested estimates
        are JSON null. testable requires a finite p-value and converged LFC.
        p_value is unadjusted: a separate full-family FDR step is required.

    Limits:
        Observational replicated bulk-count analysis only; not single-cell,
        compositional percentages, transformed values, or causal inference. At
        most 60000 genes, 64 samples and 2 million cells; at least 20 nonzero genes
        are required as an explicit wrapper normalization/trend guard. One CPU.
        An explicit existing SCITOOLFLOW_ARTIFACTS_DIR is required. The harness
        should grant this full-file fit up to 900 s rather than discard genes.
    """
    import numpy as np
    import pandas as pd
    from filelock import FileLock
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats
    from threadpoolctl import threadpool_limits
    from src.utils.paths import local_root
    from tools.implementations.general.research_data import (
        _public_source_path,
        _task_artifacts_root,
    )

    started = time.monotonic()
    artifact_root = _task_artifacts_root()
    counts_path = _public_source_path(counts_file)
    metadata_path = _public_source_path(metadata_file)
    if (
        not isinstance(design_factors, list)
        or not design_factors
        or any(not isinstance(x, str) or not x for x in design_factors)
        or len(set(design_factors)) != len(design_factors)
        or len(design_factors) > 6
    ):
        raise ValueError("design_factors requires 1 to 6 unique nonempty column names")
    # Additive terms commute mathematically. A fixed order also fixes numerical
    # optimizer paths, convergence flags and the eligible hypothesis family.
    design_factors = sorted(design_factors)
    if (
        not isinstance(contrast, list)
        or len(contrast) != 3
        or any(not isinstance(x, str) or not x for x in contrast)
        or contrast[0] not in design_factors
        or contrast[1] == contrast[2]
    ):
        raise ValueError(
            "contrast requires [design factor, distinct tested level, reference level]"
        )
    for field, value in [
        ("sample_id_column", sample_id_column),
        ("gene_id_column", gene_id_column),
    ]:
        if not isinstance(value, str) or not value:
            raise ValueError(field + " must be a nonempty string")
    if sample_id_column in design_factors:
        raise ValueError("Sample identity is not a categorical design factor")
    if not isinstance(metadata_id_suffix, str):
        raise ValueError("metadata_id_suffix must be a string")
    if fit_type not in ("parametric", "mean"):
        raise ValueError("fit_type must be parametric or mean")
    if type(cooks_filter) is not bool or type(use_cache) is not bool:
        raise ValueError("cooks_filter and use_cache must be booleans")
    ch, cr, counts_sha = _table(counts_path, "\t")
    mh, mr, metadata_sha = _table(metadata_path, ",")
    if gene_id_column not in ch or sample_id_column not in mh:
        raise ValueError("Requested gene/sample identity column is absent")
    if any(field not in mh for field in design_factors):
        raise ValueError("A requested design factor is absent from metadata")
    gene_index, sample_index = ch.index(gene_id_column), mh.index(sample_id_column)
    samples = [name for i, name in enumerate(ch) if i != gene_index]
    genes = [row[gene_index] for row in cr]
    if (
        not (1 <= len(genes) <= 60000 and 4 <= len(samples) <= 64)
        or len(genes) * len(samples) > 2000000
    ):
        raise ValueError(
            "Counts require 1..60000 genes, 4..64 samples, and <=2000000 cells"
        )
    if len(set(genes)) != len(genes) or any(not gene for gene in genes):
        raise ValueError("Gene IDs must be unique nonempty strings")
    metadata = {}
    sample_mapping = []
    for row in mr:
        original = row[sample_index]
        if not original or (
            metadata_id_suffix and not original.endswith(metadata_id_suffix)
        ):
            raise ValueError(
                "Every metadata sample ID must be nonempty and have the declared suffix"
            )
        sample = (
            original[: -len(metadata_id_suffix)] if metadata_id_suffix else original
        )
        if not sample or sample in metadata:
            raise ValueError(
                "Metadata sample IDs are empty or duplicate after explicit suffix removal"
            )
        record = dict(zip(mh, row))
        if any(not record[factor] for factor in design_factors):
            raise ValueError("Categorical design factors may not be missing or empty")
        metadata[sample] = record
        sample_mapping.append({"metadata_id": original, "count_sample_id": sample})
    if set(metadata) != set(samples):
        raise ValueError(
            "Metadata and count sample IDs must match exactly before subsetting"
        )
    values = []
    for row in cr:
        parsed = []
        for i, text in enumerate(row):
            if i == gene_index:
                continue
            # A lexical integer guard prevents float rounding, NaN, bool, and
            # accidental exponent notation from being mistaken for raw counts.
            if not text or not text.isascii() or not text.isdecimal():
                raise ValueError(
                    "Raw counts must be nonnegative decimal integers; no rounding or imputation"
                )
            number = int(text)
            if number > 2**31 - 1:
                raise ValueError("Individual raw counts must be <=2147483647")
            parsed.append(number)
        values.append(parsed)
    original_counts = np.asarray(values, dtype=np.int64)
    if sample_subset is None:
        selected = samples[:]
    elif (
        isinstance(sample_subset, list)
        and 4 <= len(sample_subset) <= len(samples)
        and all(isinstance(x, str) and x in samples for x in sample_subset)
        and len(set(sample_subset)) == len(sample_subset)
    ):
        # Canonicalize to source order to keep fits independent of caller order.
        selected = [sample for sample in samples if sample in set(sample_subset)]
    else:
        raise ValueError(
            "sample_subset must be null or >=4 unique exact count sample IDs"
        )
    matrix = original_counts[:, [samples.index(sample) for sample in selected]]
    if np.any(matrix.sum(axis=0) == 0):
        raise ValueError("Every fitted sample must have positive total raw counts")
    nonzero = matrix.sum(axis=1) > 0
    if int(nonzero.sum()) < 20:
        raise ValueError(
            "This wrapper requires at least 20 nonzero genes for normalization/trend fitting"
        )
    encoded = pd.DataFrame(index=selected)
    level_mapping, factor_mapping = {}, {}
    rank_parts = [np.ones((len(selected), 1))]
    for i, factor in enumerate(design_factors):
        levels = sorted({metadata[sample][factor] for sample in selected})
        if len(levels) < 2:
            raise ValueError(
                "Each fitted design factor must have >=2 levels; remove constant nuisance factors explicitly"
            )
        factor_mapping[factor] = "f" + str(i)
        level_mapping[factor] = {level: "L" + str(j) for j, level in enumerate(levels)}
        encoded[factor_mapping[factor]] = [
            level_mapping[factor][metadata[sample][factor]] for sample in selected
        ]
        rank_parts.extend(
            np.array(
                [[float(metadata[sample][factor] == level)] for sample in selected]
            )
            for level in levels[1:]
        )
    contrast_factor, tested, reference = contrast
    if any(
        level not in level_mapping[contrast_factor] for level in (tested, reference)
    ):
        raise ValueError("Contrast levels are absent from fitted metadata")
    contrast_sizes = {
        level: sum(metadata[sample][contrast_factor] == level for sample in selected)
        for level in (tested, reference)
    }
    if min(contrast_sizes.values()) < 2:
        raise ValueError("Each contrast level requires at least two fitted samples")
    design = np.column_stack(rank_parts)
    design_rank = int(np.linalg.matrix_rank(design))
    if design_rank != design.shape[1]:
        raise ValueError(
            "Additive design is rank deficient/confounded; the requested effects are not identifiable"
        )
    residual_df = len(selected) - design_rank
    if residual_df < 2:
        raise ValueError("At least two residual degrees of freedom are required")
    versions = {
        name: importlib.metadata.version(name)
        for name in ("pydeseq2", "anndata", "numpy", "scipy", "pandas", "scikit-learn")
    }
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    params = {
        "counts_sha256": counts_sha,
        "metadata_sha256": metadata_sha,
        "design_factors": design_factors,
        "contrast": contrast,
        "sample_id_column": sample_id_column,
        "gene_id_column": gene_id_column,
        "metadata_id_suffix": metadata_id_suffix,
        "fitted_sample_ids": selected,
        "fit_type": fit_type,
        "cooks_filter": cooks_filter,
        "versions": versions,
        "implementation_sha256": source_sha,
    }
    cache_key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    cache_root = local_root() / "cache/bulk_rnaseq_counts"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_file = cache_root / (cache_key + ".json")
    cache_hit = False
    with FileLock(str(cache_file) + ".lock", timeout=900):
        if use_cache and cache_file.is_file():
            document = json.loads(cache_file.read_text())
            cache_hit = True
        else:
            frame = pd.DataFrame(matrix.T, index=selected, columns=genes)
            output = io.StringIO()
            encoded_contrast = [
                factor_mapping[contrast_factor],
                level_mapping[contrast_factor][tested],
                level_mapping[contrast_factor][reference],
            ]
            with (
                warnings.catch_warnings(record=True) as caught,
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(output),
                threadpool_limits(limits=1),
            ):
                warnings.simplefilter("always")
                dds = DeseqDataSet(
                    counts=frame,
                    metadata=encoded,
                    design_factors=list(factor_mapping.values()),
                    # Hold model coding fixed across contrast reversals. Changing
                    # the fitted reference perturbs optimizer paths (and a few
                    # difficult genes' dispersion estimates). DeseqStats handles
                    # the requested signed contrast on the same canonical fit.
                    fit_type=fit_type,
                    refit_cooks=False,
                    n_cpus=1,
                    quiet=True,
                )
                dds.deseq2()
                stats = DeseqStats(
                    dds,
                    contrast=encoded_contrast,
                    cooks_filter=cooks_filter,
                    independent_filter=False,
                    quiet=True,
                )
                stats.summary()
            size_factors = np.asarray(dds.obsm["size_factors"]).reshape(-1)
            if (
                len(size_factors) != len(selected)
                or not np.isfinite(size_factors).all()
                or np.any(size_factors <= 0)
            ):
                raise RuntimeError("Count model produced invalid normalization factors")
            converged = np.asarray(dds.varm["_LFC_converged"]).reshape(-1)
            rows = []
            for i, gene in enumerate(genes):
                result = stats.results_df.loc[gene]
                convergence = (
                    None if not np.isfinite(converged[i]) else bool(converged[i])
                )
                p_value = _finite(result["pvalue"])
                testable = p_value is not None and convergence is True
                status = (
                    "tested"
                    if testable
                    else (
                        "all_zero"
                        if not nonzero[i]
                        else (
                            "fit_not_converged"
                            if convergence is not True
                            else "library_filtered_or_undefined"
                        )
                    )
                )
                rows.append(
                    {
                        "gene_id": gene,
                        "base_mean": _finite(result["baseMean"]),
                        "log2_fold_change": _finite(result["log2FoldChange"]),
                        "log2_standard_error": _finite(result["lfcSE"]),
                        "wald_statistic": _finite(result["stat"]),
                        "p_value": p_value,
                        "lfc_converged": convergence,
                        "testable": testable,
                        "test_status": status,
                    }
                )
            diagnostics = {}
            for field in ("_genewise_converged", "_MAP_converged", "_LFC_converged"):
                flags = np.asarray(dds.varm[field]).reshape(-1)
                diagnostics[field.lstrip("_")] = {
                    "converged": int(np.sum(flags == 1)),
                    "not_converged": int(np.sum(flags == 0)),
                    "undefined": int(np.sum(~np.isfinite(flags))),
                }
            document = {
                "data": rows,
                "model": {
                    **params,
                    "input_gene_count": len(genes),
                    "tested_gene_count": sum(row["testable"] for row in rows),
                    "input_sample_ids": samples,
                    "sample_id_mapping": sample_mapping,
                    "design_rank": design_rank,
                    "residual_degrees_of_freedom": residual_df,
                    "contrast_sample_sizes": contrast_sizes,
                    "factor_encoding": factor_mapping,
                    "level_encoding": level_mapping,
                    "size_factors": dict(zip(selected, map(float, size_factors))),
                    "dispersion_trend_requested": fit_type,
                    "dispersion_trend_actual": str(dds.uns["disp_function_type"]),
                    "normalization": (
                        "iterative_library_fallback"
                        if bool((matrix == 0).any(axis=1).all())
                        else "median_of_ratios"
                    ),
                    "test": "two_sided_Wald_H0_log2FC_0",
                    "p_value_adjustment": "none_exposed; separate_full_family_FDR_required",
                    "independent_filter": False,
                    "lfc_shrinkage": False,
                    "count_replacement": False,
                    "fit_diagnostics": diagnostics,
                    "warnings": sorted({str(w.message) for w in caught}),
                    "interpretation_scope": "Replicated historical bulk-count association; no causal or functional mechanism claim",
                    "gene_universe_policy": "all supplied genes fitted together; all rows retained including untested/null; no gene preselection",
                    "recommended_fdr_eligibility_field": "testable",
                    "fit_elapsed_seconds": time.monotonic() - started,
                },
            }
            if not any(row["testable"] for row in rows):
                raise RuntimeError(
                    "No converged gene has a finite Wald p-value; inspect design and counts"
                )
            if use_cache:
                temporary = cache_file.with_suffix("." + uuid.uuid4().hex + ".tmp")
                temporary.write_text(
                    json.dumps(document, allow_nan=False, separators=(",", ":"))
                )
                temporary.replace(cache_file)
    destination = artifact_root / "bulk_rnaseq" / uuid.uuid4().hex
    destination.mkdir(parents=True)
    result_path = destination / "results.json"
    raw = json.dumps(document, allow_nan=False, separators=(",", ":")).encode()
    result_path.write_bytes(raw)
    result_sha = hashlib.sha256(raw).hexdigest()
    result_path.with_suffix(".provenance.json").write_text(
        json.dumps(
            {
                "raw_sha256": result_sha,
                "source_type": "derived_statistical_result",
                "counts_sha256": counts_sha,
                "metadata_sha256": metadata_sha,
                "method": "PyDESeq2",
                "versions": versions,
                "implementation_sha256": source_sha,
                "not_an_official_source_snapshot": True,
            },
            indent=2,
        )
    )
    return {
        "results_file": str(result_path),
        "results_sha256": result_sha,
        "gene_count": len(document["data"]),
        "tested_gene_count": document["model"]["tested_gene_count"],
        "model": document["model"],
        "preview": document["data"][:5],
        "cache_hit": cache_hit,
        "elapsed_seconds": time.monotonic() - started,
    }
