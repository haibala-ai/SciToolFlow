"""One public operation per statistical family, with inline or artifact adapters."""


def adjust_p_values(p_values: list | None = None, method: str = 'bh', results_file: str | None = None, id_field: str = 'gene_id', p_value_field: str = 'p_value', eligibility_field: str | None = None) -> dict:
    """Correct one explicitly supplied complete hypothesis family.

    Supply exactly one of a 1..10000 nonnull P-value list or an uploaded JSON
    results_file. File mode retains up to60000 unique string-ID records, nulls,
    strict Boolean eligibility and SHA256 provenance in a complete artifact.
    Inline mode returns adjusted values in source order. File-field parameters
    are invalid in inline mode. No filtering, omitted-test inference or cutoff
    selection occurs. BH requires independence/positive dependence; BY supports
    arbitrary dependence; Bonferroni controls FWER. Both modes share one kernel.
    """
    if (p_values is None) == (results_file is None):
        raise ValueError('Supply exactly one of p_values or results_file')
    if results_file is not None:
        from .file_statistics import adjust_p_values_file
        return adjust_p_values_file(results_file, method, id_field, p_value_field, eligibility_field)
    if id_field != 'gene_id' or p_value_field != 'p_value' or eligibility_field is not None:
        raise ValueError('File field parameters cannot be applied to an inline vector')
    from .research_workflows import adjust_p_values as inline
    return inline(p_values, method)


def hypergeometric_enrichment(universe_ids: list | None = None, selected_ids: list | None = None, term_members: dict | None = None, universe_file: str | None = None, selected_file: str | None = None, membership_file: str | None = None, universe_id_field: str = 'gene_id', selected_id_field: str = 'gene_id', term_id_field: str = 'term_id', member_id_field: str = 'gene_id', unknown_member_policy: str = 'ignore_report', preview_limit: int = 20) -> dict:
    """Test all explicitly declared sets for one-sided overrepresentation.

    Use exactly one complete input form: universe_ids/selected_ids/term_members
    or universe_file/selected_file/membership_file. IDs are nonempty strings;
    universe and selection have no duplicates, selection is a universe subset,
    empty selection and empty term sets are valid, and duplicate memberships
    are deduplicated. No background, annotation or family member is inferred.
    Inline limits:10000 universe IDs,1000 terms,250000 membership entries.
    File limits and full artifacts follow the file adapter:60000 universe rows,
    declared term_ids, SHA256 provenance, bounded preview. All declared terms
    receive an unadjusted P(X>=observed) from the same tail kernel; outside
    members are ignored+reported or rejected. No correction or cutoff is chosen.
    """
    inline_values = [universe_ids, selected_ids, term_members]
    file_values = [universe_file, selected_file, membership_file]
    use_inline = all(v is not None for v in inline_values) and all(v is None for v in file_values)
    use_file = all(v is None for v in inline_values) and all(v is not None for v in file_values)
    if not (use_inline or use_file):
        raise ValueError('Supply exactly one complete inline or file input form')
    if unknown_member_policy not in {'ignore_report', 'error'}:
        raise ValueError('unknown_member_policy must be ignore_report or error')
    if type(preview_limit) is not int or not 0 <= preview_limit <= 100:
        raise ValueError('preview_limit must be an integer in 0..100')
    if use_file:
        from .file_enrichment import hypergeometric_enrichment_file
        return hypergeometric_enrichment_file(universe_file, selected_file, membership_file, universe_id_field, selected_id_field, term_id_field, member_id_field, unknown_member_policy, preview_limit)
    if [universe_id_field, selected_id_field, term_id_field, member_id_field] != ['gene_id', 'gene_id', 'term_id', 'gene_id']:
        raise ValueError('File field parameters cannot be applied to inline sets')
    for values, label in [(universe_ids, 'universe_ids'), (selected_ids, 'selected_ids')]:
        if not isinstance(values, list) or len(values) > 10000 or any(not isinstance(x, str) or not x for x in values) or len(set(values)) != len(values):
            raise ValueError(label + ' requires at most10000 distinct nonempty string IDs')
    u, selected = set(universe_ids), set(selected_ids)
    if not u or not selected <= u:
        raise ValueError('Require nonempty universe and selection subset')
    if not isinstance(term_members, dict) or not 1 <= len(term_members) <= 1000:
        raise ValueError('term_members requires1..1000 explicit terms')
    from .statistical_kernels import enrichment_tail
    rows = []
    cells = 0
    for term, ids in term_members.items():
        if not isinstance(term, str) or not term or not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
            raise ValueError('Term and member IDs must be nonempty strings')
        cells += len(ids)
        if cells > 250000:
            raise ValueError('At most250000 inline membership entries')
        members = set(ids)
        outside = members - u
        if outside and unknown_member_policy == 'error':
            raise ValueError('Term members outside explicit universe')
        within, overlap = members & u, members & selected
        N, K, n, k = len(u), len(within), len(selected), len(overlap)
        rows.append(dict(term_id=term, N=N, K=K, n=n, k=k, overlap_ids=sorted(overlap), outside_universe_member_ids=sorted(outside), **enrichment_tail(N, K, n, k)))
    return dict(universe_size=len(u), selected_size=len(selected), family_size=len(rows), results=rows, p_values=[r['p_value'] for r in rows], test='One-sided hypergeometric P(X>=observed); unadjusted; complete declared family')
