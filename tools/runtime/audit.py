"""Opt-in read isolation for benchmark construction; inactive for normal Agent runs."""

import json
import os
from pathlib import Path
import sys
import threading

_installed = False


def install():
    global _installed
    destination = os.getenv("SCITOOL_CONSTRUCTION_READ_AUDIT")
    if not destination or _installed:
        return
    from src.utils.paths import project_root

    root = project_root()
    directory = Path(destination).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / ("reads-" + str(os.getpid()) + ".jsonl")
    state = threading.local()
    seen = set()

    def audit(event, arguments):
        if event != "open" or getattr(state, "busy", False):
            return
        target = arguments[0]
        if not isinstance(target, (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(target)).resolve()
        text = str(path)
        forbidden = (
            root / "tools/graph" == path
            or root / "tools/graph" in path.parents
            or path.name in {"your_tool_KG.xlsx", "tools_metadata.json"}
            or "storage_graph_large" in path.parts
            or (root / "tools/implementations/biology") in path.parents
        )
        if not forbidden and root not in path.parents:
            return
        signature = (text, str(arguments[1]))
        if signature not in seen or forbidden:
            state.busy = True
            try:
                fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    os.write(
                        fd,
                        (
                            json.dumps(
                                {
                                    "pid": os.getpid(),
                                    "path": text,
                                    "mode": str(arguments[1]),
                                    "blocked": forbidden,
                                }
                            )
                            + "\n"
                        ).encode(),
                    )
                finally:
                    os.close(fd)
                seen.add(signature)
            finally:
                state.busy = False
        if forbidden:
            raise PermissionError(
                "Benchmark construction cannot read KG-derived or biological sources"
            )

    sys.addaudithook(audit)
    _installed = True
