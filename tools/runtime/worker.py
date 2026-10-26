"""Execute one tool inside its assigned environment and return a structured result."""

import contextlib
import json
import sys
import traceback
from tools.runtime.audit import install

install()
from tools.runtime.dispatch import REGISTRY, invoke_here, validate_result
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
        result = validate_result(output, REGISTRY["tools"][request["tool"]])
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
    except (InputValidationError, ValueError, TypeError, SyntaxError) as error:
        result = {
            "status": "error",
            "output": None,
            "error_type": "InvalidInput",
            "error": str(error),
        }
    except Exception as error:
        import requests

        if isinstance(error, (requests.Timeout, requests.ConnectionError)):
            category, state = "UpstreamConnectionError", "blocked"
        elif isinstance(error, requests.HTTPError):
            code = error.response.status_code if error.response is not None else None
            category = (
                "UpstreamRateLimit"
                if code == 429
                else (
                    "UpstreamAuthenticationRequired"
                    if code in {401, 403}
                    else "UpstreamHTTPError"
                )
            )
            state = (
                "blocked"
                if code in {401, 403, 429} or code is not None and code >= 500
                else "error"
            )
        else:
            category, state = type(error).__name__, "error"
            traceback.print_exc(file=sys.stderr)
        result = {
            "status": state,
            "output": None,
            "error_type": category,
            "error": str(error),
        }
    print(
        json.dumps({"toolkg_result": result}, default=str, allow_nan=False), flush=True
    )
