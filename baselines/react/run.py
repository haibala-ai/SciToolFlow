"""Run the ReAct baseline; arguments are identical to `cli.py run`."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scitoolflow.cli import main

if __name__ == "__main__":
    # This entry always selects ReAct; SciToolAgent has its own adjacent entry.
    if "--baseline" in sys.argv or any(a.startswith("--baseline=") for a in sys.argv):
        raise SystemExit("Use cli.py run --baseline ... to select another baseline")
    sys.argv.insert(1, "run")
    main()
