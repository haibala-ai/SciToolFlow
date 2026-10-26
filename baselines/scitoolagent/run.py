"""Run the SciToolAgent baseline with the shared benchmark CLI."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cli import main

if __name__ == "__main__":
    if "--baseline" in sys.argv or any(a.startswith("--baseline=") for a in sys.argv):
        raise SystemExit("Use cli.py run --baseline ... to select another baseline")
    sys.argv[1:1] = ["run", "--baseline", "scitoolagent"]
    main()
