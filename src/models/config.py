"""Only the deployment settings required by the optional local model worker."""

import os
from src.utils.paths import local_root, project_root, load_environment
from tools.runtime.environments import environment_python


class Config:
    def __init__(self):
        load_environment()
        self.LOCAL_MODEL_PATH = os.getenv(
            "SCITOOL_MODEL_PATH", str(local_root() / "models/Qwen3.5-9B")
        )
        self.LOCAL_EMBED_PATH = os.getenv(
            "SCITOOL_EMBED_PATH", str(local_root() / "models/Qwen3-Embedding-0.6B")
        )
        self.LLM_PYTHON = os.getenv(
            "SCITOOL_LLM_PYTHON", str(environment_python("SciTool-LLM"))
        )
        self.TRACE_DIR = project_root() / "results/model_logs"
