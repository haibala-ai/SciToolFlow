"""Controlled SciMas runtime ablations; scientific tools and graders are shared."""

from .policy import VARIANTS, AblationPolicy, resolve_ablation

__all__ = ["VARIANTS", "AblationPolicy", "resolve_ablation"]
