import os

broker_url = os.getenv("CELERY_BROKER_URL", "amqp://ubuntu:ubuntu@broker:5672//")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://:ubuntu@redis:6379/0")

accept_content = ["json"]
task_serializer = "json"
result_serializer = "json"

task_ignore_result = False

task_track_started = True

worker_hijack_root_logger = False

task_routes = {
    "tasks.product_prediction": {"queues": "product_prediction"},
    "tasks.retro_prediction": {"queues": "retro_prediction"},
    "tasks.retro_prediction_tree": {"queues": "retro_prediction"},
}
