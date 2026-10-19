"""
Update this script and run it inside the worker container to run your retrosynthesis predictions via script
"""
print("Setting up retrosynthesis prediction...")

# All necessary imports
from celery import Celery
from utils import wait_for_result

# Initialize Celery
celery_app = Celery()
print("Broker:", celery_app.conf.broker_url)
print("Backend:", celery_app.conf.result_backend)

# Choose product for retrosynthesis prediction
product = "C=CC(=C)C[Si](C)(C)C"

# Setup task kwargs
kwargs = {
    "topn": 15,       # Number of results per reactant
    "num_beams": 15,  # Number of beams used for prediction. Must be >= topn
    "fap": 0.6,       # Forward likelihood acceptance probability (not length averaged)
    "fld": 0.2,       # Forward likelihood delta required between the top2 forward prediction results
    "device": None,   # Device used for predicting, either "cuda" or "cpu", None defaults to cuda if available
    "ckpt_forward": "Pistachio2025Q2-Forward",  # Default forward model
    "ckpt_retro": "Pistachio2025Q2-Retro",    # Default retrosynthesis model
    "vocab": "Pistachio2025Q2",         # Vocab for default forward and retrosynthesis models
    # "ckpt_forward_path": "models/forward/Pistachio2025Q2-Forward.ckpt",  # Can be used instead of ckpt_forward
    # "ckpt_retro_path": "models/retrosynthesis/Pistachio2025Q2-Retro.ckpt",  # Can be used instead of ckpt_retro
    # "vocab_path": "vocab/Pistachio2025Q2.txt",  # Can be used instead of vocab
}

# Send the retro_prediction task with the product and kwargs
task = celery_app.send_task(
    "tasks.retro_prediction",
    [product],
    kwargs=kwargs,
    queue="retro_prediction",
)
print("Task sent. Assigned task_id: {}".format(task.id))

# Use the task id to get the result. Increase timeout if needed.
wait_for_result(celery_app, task.id, timeout=300)
