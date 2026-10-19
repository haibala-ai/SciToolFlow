"""
Update this script and run it inside the worker container to run your retrosynthesis tree predictions via script
"""
print("Setting up retrosynthesis tree prediction...")

# All necessary imports
from celery import Celery
from utils import wait_for_result

# Initialize Celery
celery_app = Celery()
print("Broker:", celery_app.conf.broker_url)
print("Backend:", celery_app.conf.result_backend)

# Choose product for retrosynthesis tree prediction
product = "C1C(C[Si](C)(C)C)=CCC2C(=O)OC(=O)C12"
#product = "Cc1cc2scnc2cc1N"
#product = "CC(C)(C(=O)O)C1C=CC=C(C2CC2)C1=O"
#product = "Nc1ccc2scnc2c1Br"

# Setup task kwargs
kwargs = {
    "topn": 15,       # Number of results per reactant
    "num_beams": 15,  # Number of beams used for prediction. Must be >= topn
    "fap": 0.6,       # Forward likelihood acceptance probability (not length averaged)
    "fld": 0.2,       # Forward likelihood delta required between the top2 forward prediction results
    "max_depth": 4,   # Max depth of the retrosynthesis tree
    "beam_width": 6,  # Max amount of nodes being expanded in each step
    "device": None,   # Device used for predicting, either "cuda" or "cpu", None defaults to cuda if available
    "ckpt_forward": "Pistachio2025Q2-Forward",  # Default forward model
    "ckpt_retro": "Pistachio2025Q2-Retro",    # Default retrosynthesis model
    "vocab": "Pistachio2025Q2",         # Vocab for default forward and retrosynthesis models
    # "ckpt_forward_path": "models/forward/Pistachio2025Q2-Forward.ckpt",  # Can be used instead of ckpt_forward
    # "ckpt_retro_path": "models/retrosynthesis/Pistachio2025Q2-Retro.ckpt",  # Can be used instead of ckpt_retro
    # "vocab_path": "vocab/Pistachio2025Q2.txt",  # Can be used instead of vocab
}

# Send the retro_prediction_tree task with the product and kwargs
task = celery_app.send_task(
    "tasks.retro_prediction_tree",
    [product],
    kwargs=kwargs,
    queue="retro_prediction",
)
print("Task sent. Assigned task_id: {}".format(task.id))

# Use the task id to get the result. Increase timeout if needed.
wait_for_result(celery_app, task.id, timeout=3000)
