"""Named, immutable interventions on the same SciMas implementation."""

from dataclasses import asdict, dataclass

from ..experience import Experience


@dataclass(frozen=True)
class AblationPolicy:
    variant: str = "full"
    experience: bool = True
    parallel: bool = True
    early_stop: bool = True
    local_repair: bool = True

    def document(self):
        return {
            "schema_version": "scimas.ablation.v1",
            **asdict(self),
            "experience_scope": "task_local",
            "serial_order": "stable_topological_plan_order",
            "unrecoverable_error_policy": (
                "bounded_local_repair" if self.local_repair else "fail_task"
            ),
        }

    def apply(self, settings):
        effective = dict(settings)
        if not self.parallel:
            effective["tool_concurrency"] = 1
        if not self.local_repair:
            effective["local_repairs"] = 0
        return effective

    def instructions(self):
        if self.variant == "full":
            return ""
        lines = [
            "Execution policy for this run is supplied in context.execution_policy. "
            "Scientific correctness, tool contracts, evidence provenance and complete "
            "final reporting are required in every variant."
        ]
        if not self.early_stop:
            lines.append(
                "Candidate screening is observational: review and report the original "
                "when predicates, but execute their downstream computations even when "
                "a resolved predicate is false. Do not delete, reject, repair away or "
                "stop a branch solely because a candidate fails screening. A computed "
                "result does not make a screened-out candidate scientifically eligible. "
                "Use gate_states and actual evidence when reporting eligibility. Missing "
                "data, invalid inputs and incorrect outputs remain errors."
            )
        if not self.parallel:
            lines.append(
                "Execution is serial in stable topological plan order. Dispatch the "
                "single ready node provided by the scheduler; do not request a graph "
                "rewrite merely to restore parallel execution."
            )
        if not self.local_repair:
            lines.append(
                "Adaptive graph replanning is disabled after scientific execution starts. "
                "The common pre-execution graph refinement and review remain available. An unrecoverable "
                "execution error or required graph correction terminates the task. "
                "Do not hide errors or substitute unsupported answers to avoid failure. "
                "Bounded automatic transient retries, inspection and answer-format "
                "correction remain available; execution-stage repair requests terminate the task."
            )
        if not self.experience:
            lines.append(
                "Procedural experience accumulation and retrieval are disabled. "
                "Use the current task graph, public contracts and observations."
            )
        return "\n\n" + "\n\n".join(lines)


VARIANTS = {
    "full": AblationPolicy(),
    "wo-exp": AblationPolicy("wo-exp", experience=False),
    "wo-parallel": AblationPolicy("wo-parallel", parallel=False),
    "wo-early-stop": AblationPolicy("wo-early-stop", early_stop=False),
    "wo-local-repair": AblationPolicy("wo-local-repair", local_repair=False),
    # The combined baseline disables all four mechanisms.
    "wo-all": AblationPolicy(
        "wo-all", experience=False, parallel=False, early_stop=False, local_repair=False
    ),
}


def resolve_ablation(name="full"):
    if not isinstance(name, str) or name not in VARIANTS:
        raise ValueError("Unknown SciMas ablation: " + str(name))
    return VARIANTS[name]


def runtime_options(baseline, variant="full"):
    policy = resolve_ablation(variant)
    if baseline != "scimas":
        if policy.variant != "full":
            raise ValueError("SciMas ablations require baseline=scimas")
        return {}
    return {"scimas_ablation": policy.variant}


class DisabledExperience(Experience):
    """Neither accumulate nor supply procedural experience, even after success."""

    def confirm(self, role, tool, contract, operation, evidence):
        return None

    def match(self, role, contracts):
        return []

    def invalidate(self, tool, contract):
        return None


class LocalRepairDisabled(RuntimeError):
    """A task needs adaptive graph repair which this intervention forbids."""
