import time
from celery import Celery
from celery.result import AsyncResult
from typing import Dict, Any


# Wait for the celery result
def wait_for_result(app: Celery, task_id: str, timeout: float = 120.0, poll: float = 0.5) -> Dict[str, Any]:
    """
    Poll for a result with a timeout. If task updates state with meta (e.g., PROGRESS),
    we surface that along the way.
    """
    res = AsyncResult(task_id, app=app)
    t0 = time.time()
    last_state = None

    while True:
        state = res.state
        if state != last_state:
            print(f"State: {state} | Info: {res.info}")
            last_state = state

        if res.ready():
            # could be SUCCESS or FAILURE; .get() will raise on FAILURE
            return res.get(propagate=False)  # returns exception object if failed

        if time.time() - t0 > timeout:
            raise TimeoutError(f"Task {task_id} did not finish in {timeout} seconds.")
        time.sleep(poll)