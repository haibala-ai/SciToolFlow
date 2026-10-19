"""Execute one tool inside its assigned environment and return a structured result."""

import contextlib
import json
import sys
import traceback
from tools.runtime.audit import install

install()
from tools.runtime.dispatch import invoke_here, normalize_output
from tools.implementations.shared.materials_api import (
    MissingScientificData,
    UnavailableScientificEndpoint,
)
from tools.implementations.shared.pubchem import PubChemUnavailable
from tools.implementations.shared.common import InputValidationError


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            output = invoke_here(
                request["tool"], request["input"], request.get("files", [])
            )
        result = normalize_output(output)
    except (ImportError, ModuleNotFoundError) as error:
        result = {
            "status": "blocked",
            "output": None,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    except (
        MissingScientificData,
        UnavailableScientificEndpoint,
        PubChemUnavailable,
    ) as error:
        result = {
            "status": "blocked",
            "output": None,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    except InputValidationError as error:
        result = {
            "status": "error",
            "output": None,
            "error_type": "InvalidInput",
            "error": str(error),
        }
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        result = {
            "status": "error",
            "output": None,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    print(json.dumps({"toolkg_result": result}, default=str), flush=True)
