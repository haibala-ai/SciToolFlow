"""Release counts derived from the canonical public tool catalog."""


def tool_counts(catalog):
    """Count callable, scored and indexed populations independently."""
    scored = sum(name != "DescribeTools" for name in catalog)
    return {
        "tool_count": len(catalog),
        "scored_tool_count": scored,
        "metadata_lookup_tool_count": len(catalog) - scored,
        "graph_tool_count": sum(
            spec.get("indexing", {}).get("graph", name != "DescribeTools")
            for name, spec in catalog.items()
        ),
        "embedding_tool_count": sum(
            spec.get("indexing", {}).get("embedding", name != "DescribeTools")
            for name, spec in catalog.items()
        ),
    }
