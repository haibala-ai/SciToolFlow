"""Bounded retry for public web services used by the biology tools.

The shared project proxy and the public providers occasionally drop TLS
connections or answer 429/5xx under load.  Every biology adapter that talks to
such a service routes its HTTP calls through :func:`request_with_retries` so a
single transient failure does not turn a working tool into a reported error.
"""

import os
import random
import time

import requests

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504, 522, 524}
DEFAULT_ATTEMPTS = 4
DEFAULT_BACKOFF = 1.5
MAX_DELAY = 20.0


def _attempts():
    try:
        return max(1, int(os.getenv("SCITOOL_HTTP_ATTEMPTS", str(DEFAULT_ATTEMPTS))))
    except ValueError:
        return DEFAULT_ATTEMPTS


def _sleep_seconds(response, index):
    header = response.headers.get("Retry-After") if response is not None else None
    if header:
        try:
            return min(float(header), MAX_DELAY)
        except ValueError:
            pass
    return min(DEFAULT_BACKOFF * (2**index), MAX_DELAY) + random.random()


def request_with_retries(session, method, url, *, attempts=None, timeout=30, **kwargs):
    """Return the last response, retrying connection errors and retryable statuses.

    ``requests`` exceptions are re-raised only after every attempt is exhausted,
    so callers keep their existing error handling and the final error is the
    real provider failure rather than the first transient one.
    """
    total = attempts or _attempts()
    last_response = None
    last_error = None
    for index in range(total):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as error:
            last_error = error
            if index + 1 < total:
                time.sleep(_sleep_seconds(None, index))
                continue
            raise
        if response.status_code in RETRYABLE_STATUS and index + 1 < total:
            last_response = response
            time.sleep(_sleep_seconds(response, index))
            continue
        return response
    if last_response is not None:
        return last_response
    raise last_error
