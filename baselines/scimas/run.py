"""SciMas full-workflow entry point using the shared public benchmark runner."""

import sys
from cli import main

if __name__ == "__main__":
    sys.argv[1:1] = ["run", "--baseline", "scimas"]
    main()
