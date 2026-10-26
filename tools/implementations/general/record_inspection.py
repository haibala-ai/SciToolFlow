"""File schema/provenance inspection and one numeric column extraction API."""


def extract_numeric_columns(record_table: list, columns: list, output_shape: str = 'matrix') -> dict:
    """Extract literal finite numeric columns, preserving row and column order.

    matrix returns ordered feature rows; vector requires exactly one column.
    No missing/null/text/bool coercion, imputation or positional interpretation.
    Validation and numeric conversion share the existing bounded data kernel.
    """
    if output_shape not in {'matrix', 'vector'}:
        raise ValueError('output_shape must be matrix or vector')
    from .data_tools import extract_numeric_matrix
    answer = extract_numeric_matrix(record_table, columns)
    if output_shape == 'vector':
        if len(columns) != 1:
            raise ValueError('vector output requires exactly one named column')
        return dict(values=[row[0] for row in answer['features']], columns=list(columns), row_count=answer['row_count'], output_shape='vector')
    return dict(answer, output_shape='matrix')


def inspect_scientific_file(records_file: str) -> dict:
    """Inspect a public JSON record file's schema, count and verified provenance.

    Read at most25MiB and60000 records in a bare list or data field. Return only
    field names/types/presence counts and source SHA256, never record values.
    If a readable sibling provenance document exists, require its raw_sha256 to
    match. No record selection, field projection, typing, scientific inference
    or live-service fallback. Use QueryScientificRecordsFile to read records.
    """
    from .file_records import _load_records
    from .research_data import _public_source_path, _verified_provenance
    _, records, sha = _load_records(records_file)
    kinds = {type(None): 'null', bool: 'boolean', int: 'integer', float: 'number', str: 'string', list: 'array', dict: 'object'}
    fields = {}
    for row in records:
        for key, value in row.items():
            item = fields.setdefault(key, {'types': set(), 'present_count': 0, 'null_count': 0})
            item['types'].add(kinds[type(value)])
            item['present_count'] += 1
            item['null_count'] += value is None
    if len(fields) > 4096:
        raise ValueError('At most4096 distinct top-level fields')
    return dict(record_count=len(records), fields={key: dict(types=sorted(v['types']), present_count=v['present_count'], missing_count=len(records)-v['present_count'], null_count=v['null_count']) for key, v in sorted(fields.items())}, source_sha256=sha, verified_provenance=_verified_provenance(_public_source_path(records_file), sha), scope='Schema and provenance only; no record values or scientific model inferred')
