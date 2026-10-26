"""Explicit file-based set enrichment,independent of gene selection or annotation."""

import math

from tools.implementations.general.file_records import (
    _load_records,
    _preview,
    _write_record_artifact,
)


def hypergeometric_enrichment_file(
    universe_file: str,
    selected_file: str,
    membership_file: str,
    universe_id_field: str = "gene_id",
    selected_id_field: str = "gene_id",
    term_id_field: str = "term_id",
    member_id_field: str = "gene_id",
    unknown_member_policy: str = "ignore_report",
    preview_limit: int = 20,
) -> dict:
    """Test a complete explicitly declared file-based set family for enrichment.

    All inputs must be uploaded or explicit current-task artifact JSON objects
    with data record lists,or bare record lists where permitted. Universe and
    selection each contain0..60000 records,25 MiB maximum,with distinct nonempty
    string IDs in their explicitly named top-level fields. Universe must be
    nonempty;selected may be empty and must be a subset of universe. Duplicate
    universe or selected IDs are errors,not silently collapsed or reweighted.

    membership_file is an object with term_ids(1..1000 distinct nonempty strings)
    and data(0..250000 objects,50 MiB). Every membership row names an explicitly
    declared term_id_field and a nonempty string member_id_field. Exact repeated
    term/member pairs are deduplicated and reported;annotations must not inflate
    gene counts. All declared terms are tested,including terms with no members.
    Members outside the supplied universe are either ignored and fully reported
    under ignore_report,or cause an error under error. No background is inferred.

    For each term,N=universe size,K=within-universe distinct term members,
    n=selected size,k=selected term overlap. Returns the unadjusted one-sided
    hypergeometric upper-tail probability P(X>=k),not a two-sided association
    or depletion test. Empty selected or empty term sets have p=1. Expected
    overlap=n*K/N;fold_enrichment=k/expected is null when expectation is0.
    p_value_underflow explicitly marks floating-point zero tails;log_p_value is
    null if the library cannot represent it finitely. Zero is not claimed an
    exact mathematical probability. No NaN or infinity is emitted.

    Complete records with N,K,n,k,p_value,expected_overlap,fold_enrichment,
    overlap_ids,outside_universe_member_ids,and member counts are written
    atomically under the explicit task artifact root. Original term order,
    all declared family members,three source SHA256s and duplicate diagnostics
    are preserved. A bounded complete-record preview contains at most100 rows
    and20000 characters. AdjustPValuesFile may then adjust the entire declared
    term_id family;this function does not adjust or choose significance cutoffs.

    No automatic feature selection,gene-ID remapping,GO hierarchy propagation,
    annotation evidence filtering,assay eligibility inference,causal conclusion
    or scientific interpretation is performed. These are caller responsibilities.
    """
    from .statistical_kernels import enrichment_tail

    for key, value in [
        ("universe_id_field", universe_id_field),
        ("selected_id_field", selected_id_field),
        ("term_id_field", term_id_field),
        ("member_id_field", member_id_field),
    ]:
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError(
                key + " must be a nonempty top-level field name of length<=256"
            )
    if term_id_field == member_id_field:
        raise ValueError("Term and member fields must be different")
    if unknown_member_policy not in {"ignore_report", "error"}:
        raise ValueError("unknown_member_policy must be ignore_report or error")
    if type(preview_limit) is not int or not 0 <= preview_limit <= 100:
        raise ValueError("preview_limit must be integer0..100")
    _, urows, usha = _load_records(universe_file)
    _, srows, ssha = _load_records(selected_file)
    annotation, mrows, msha = _load_records(
        membership_file, max_rows=250000, max_bytes=50 * 1024 * 1024
    )

    def identities(rows, key):
        seen = set()
        for row in rows:
            value = row.get(key)
            if not isinstance(value, str) or not value or value in seen:
                raise ValueError(
                    "Every universe/selected record requires a distinct nonempty string ID"
                )
            seen.add(value)
        return seen

    universe = identities(urows, universe_id_field)
    selected = identities(srows, selected_id_field)
    if not universe:
        raise ValueError("Universe must contain at least one sampling unit")
    if not selected <= universe:
        raise ValueError("Selected identifiers outside explicit universe")
    terms = annotation.get("term_ids") if isinstance(annotation, dict) else None
    if (
        not isinstance(terms, list)
        or not 1 <= len(terms) <= 1000
        or any(not isinstance(term, str) or not term for term in terms)
        or len(set(terms)) != len(terms)
    ):
        raise ValueError("Membership document needs1..1000 distinct declared term_ids")
    members = {term: set() for term in terms}
    duplicates = 0
    for row in mrows:
        term, member = row.get(term_id_field), row.get(member_id_field)
        if (
            not isinstance(term, str)
            or term not in members
            or not isinstance(member, str)
            or not member
        ):
            raise ValueError(
                "Membership rows need a declared term and nonempty member string"
            )
        if member in members[term]:
            duplicates += 1
        members[term].add(member)
    outside = {term: values - universe for term, values in members.items()}
    if unknown_member_policy == "error" and any(outside.values()):
        raise ValueError("Term members outside explicit universe")
    records = []
    N, n = len(universe), len(selected)
    underflow = 0
    for term in terms:
        within = members[term] & universe
        overlap = selected & within
        K, k = len(within), len(overlap)
        tail = enrichment_tail(N, K, n, k)
        p, logp = tail["p_value"], tail["log_p_value"]
        is_underflow = tail["p_value_underflow"]
        underflow += is_underflow
        expected = tail["expected_overlap"]
        records.append(
            {
                "term_id": term,
                "N": N,
                "K": K,
                "n": n,
                "k": k,
                "p_value": p,
                "log_p_value": logp,
                "p_value_underflow": is_underflow,
                "expected_overlap": expected,
                "fold_enrichment": k / expected if expected else None,
                "overlap_ids": sorted(overlap),
                "outside_universe_member_ids": sorted(outside[term]),
                "outside_universe_member_count": len(outside[term]),
                "declared_distinct_member_count": len(members[term]),
            }
        )
    sources = {"universe": usha, "selected": ssha, "membership": msha}
    metadata = {
        "source_sha256": sources,
        "universe_size": N,
        "selected_size": n,
        "family_size": len(terms),
        "term_ids": terms,
        "membership_input_record_count": len(mrows),
        "duplicate_membership_pairs_ignored": duplicates,
        "unknown_member_policy": unknown_member_policy,
        "outside_universe_distinct_member_count": len(set().union(*outside.values())),
        "underflow_term_count": underflow,
        "tail": "one-sided greater:P(X>=observed overlap);unadjusted",
        "universe_id_field": universe_id_field,
        "selected_id_field": selected_id_field,
        "term_id_field": term_id_field,
        "member_id_field": member_id_field,
    }
    target, digest = _write_record_artifact("set_enrichment", records, metadata)
    preview, truncated = _preview(records, preview_limit)
    return {
        "results_file": target,
        "results_sha256": digest,
        "source_sha256": sources,
        "universe_size": N,
        "selected_size": n,
        "family_size": len(terms),
        "record_id_field": "term_id",
        "p_value_field": "p_value",
        "membership_input_record_count": len(mrows),
        "duplicate_membership_pairs_ignored": duplicates,
        "outside_universe_distinct_member_count": metadata[
            "outside_universe_distinct_member_count"
        ],
        "unknown_member_policy": unknown_member_policy,
        "underflow_term_count": underflow,
        "preview_records": preview,
        "preview_record_count": len(preview),
        "preview_truncated": truncated,
        "tail": "one-sided greater;unadjusted",
        "scope": "Explicit finite set enrichment only;no automatic background,selection,annotation propagation or multiple-testing adjustment",
    }
