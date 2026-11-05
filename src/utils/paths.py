"""Project paths, runtime directories and private environment loading."""

from pathlib import Path
import os
from contextvars import ContextVar

# Per-invocation overrides; never mutate process environment from worker threads.
CALL_DIRECTORIES = ContextVar("scitoolflow_call_directories", default=None)


def project_root():
    explicit = os.getenv("SCITOOLFLOW_ROOT")
    return (
        Path(explicit).expanduser().resolve()
        if explicit
        else Path(__file__).resolve().parents[2]
    )


def local_root():
    return project_root() / ".local"


def artifacts_root():
    if CALL_DIRECTORIES.get():
        return Path(CALL_DIRECTORIES.get()["artifacts"])
    value = os.getenv("SCITOOLFLOW_ARTIFACTS_DIR")
    return Path(value).resolve() if value else project_root() / "results/tool_artifacts"


def work_root():
    if CALL_DIRECTORIES.get():
        return Path(CALL_DIRECTORIES.get()["work"])
    value = os.getenv("SCITOOLFLOW_WORK_DIR")
    return Path(value).resolve() if value else local_root() / "work/tools"


def load_environment():
    from dotenv import load_dotenv

    root = project_root()
    load_dotenv(root / ".local/credentials/services.env", override=False)
    load_dotenv(root / ".local/credentials/runtime.env", override=False)
    os.environ.setdefault(
        "SCITOOL_ENV_FILE", str(root / ".local/credentials/services.env")
    )


def bootstrap_runtime():
    load_environment()
    os.environ.setdefault("SCITOOL_TOOL_SCOPE", "all")
    return project_root()
