"""
Update this script and run it inside the worker container to run your product predictions via script
"""
print("Setting up product prediction...")

# All necessary imports
from celery import Celery
from utils import wait_for_result

# Initialize Celery
celery_app = Celery()
print("Broker:", celery_app.conf.broker_url)
print("Backend:", celery_app.conf.result_backend)

# Set up a list of reactants to make predictions
reactants_list = ["CCI.O=Cc1ccc([N+](=O)[O-])c(O)c1", "CCOc1cc(O)c(C=O)cc1OCC.OCCCBr", "C=CCc1cc(OCc2ccccc2)ccc1O.CCBr"]

# Setup task kwargs
kwargs = {
    "topn": 1,        # Number of results per reactant
    "num_beams": 3,   # Number of beams used for prediction. Must be >= topn
    "device": None,   # Device used for predicting, either "cuda" or "cpu", None defaults to cuda if available
    "ckpt_forward": "Pistachio2025Q2-Forward",  # Default forward model
    "vocab": "Pistachio2025Q2",         # Vocab for default forward model
    # "ckpt_forward_path": "models/forward/Pistachio2025Q2-Forward.ckpt",  # Can be used instead of ckpt_forward
    # "vocab_path": "vocab/Pistachio2025Q2.txt",  # Can be used instead of vocab
}

# Send the product_prediction task with the reaction list and kwargs
task = celery_app.send_task(
    "tasks.product_prediction",
    [reactants_list],
    kwargs=kwargs,
    queue="product_prediction",
)
print("Task sent. Assigned task_id: {}".format(task.id))

# Use the task id to get the result. Increase timeout if needed.
wait_for_result(celery_app, task.id, timeout=180)
