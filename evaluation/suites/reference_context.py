"""Read reviewed scientific observations without borrowing the actor's route."""
from pathlib import Path
from evaluation.integrity.traces import execution_calls, read_trajectory


def prediction_from_reference(root, reference):
    trace = read_trajectory(Path(root) / reference['reference_trace'])
    return {'id': trace['task_id'], 'dataset': trace.get('dataset', 'full'),
            'status': trace['status'], 'completed': trace['status'] == 'completed',
            'failure_reason': trace.get('failure_reason'),
            'final_answer': trace['final_answer'], 'calls': execution_calls(trace)}
