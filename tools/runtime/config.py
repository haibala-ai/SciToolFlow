import os
from pathlib import Path
from contextvars import ContextVar
from dotenv import load_dotenv
from scitoolflow.paths import local_root, load_environment

load_environment()

UPLOAD_CONTEXT = ContextVar("scitool_upload_context", default={})


class Config:
    def __init__(self):
        self.OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

        self.BING_SUBSCRIPTION_KEY = os.getenv("BING_SUBSCRIPTION_KEY")
        self.BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")
        self.BING_SEARCH_URL = os.getenv("BING_SEARCH_URL")
        self.WOLFRAM_ALPHA_APPID = os.getenv("WOLFRAM_ALPHA_APPID")

        self.MP_KEY = os.getenv("MP_KEY")
        self.CHEMSPIDER_API_KEY = os.getenv("CHEMSPIDER_API_KEY")
        self.MODEL_NAME = os.getenv("MODEL_NAME")
        self.FORCEGPT_MODEL_PATH = os.getenv(
            "FORCEGPT_MODEL_PATH", str(local_root() / "models/ProteinForceGPT")
        )
        self.ESMFOLD_MODEL_PATH = os.getenv(
            "ESMFOLD_MODEL_PATH", str(local_root() / "models/esmfold_v1")
        )
        self.OMEGAFOLD_MODEL_PATH = os.getenv(
            "OMEGAFOLD_MODEL_PATH", str(local_root() / "models/OmegaFold")
        )
        self.DEEPTMHMM_MODEL_PATH = os.getenv(
            "DEEPTMHMM_MODEL_PATH",
            str(local_root() / "external_sources/DeepTMHMM2/checkpoints"),
        )
        self.RASPA_EXECUTABLE_PATH = os.getenv(
            "RASPA_EXECUTABLE_PATH",
            str(local_root() / "external_sources/RASPA2/install/bin/simulate"),
        )
        self.QizhiPei_MODEL_PATH = os.getenv(
            "QizhiPei_MODEL_PATH", str(local_root() / "models")
        )

        self.BASE_URL_EXPASY = "https://web.expasy.org"
        self.BASE_URL_PRABI = "https://npsa-prabi.ibcp.fr"
        self.BASE_URL_NOVOPRO = "https://www.novopro.cn/plus/tmp/"

        self.PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov"
        self.RXN4CHEM_API_KEY = os.getenv("RXN4CHEM_API_KEY")
        self.RXN4CHEM_BASE_URL = "https://rxn.res.ibm.com"
        self.RXN4CHEM_PROJECT_ID = os.getenv("RXN4CHEM_PROJECT_ID")
        self.RXN_SANDBOX_MODEL_PATH = str(local_root() / "models/rxn-sandbox")

        self.AEOPP_EXECUTABLE = os.getenv("AEOPP_EXECUTABLE")
        self.SOLVENT_THERMAL_MODELS = os.getenv(
            "SOLVENT_THERMAL_MODELS", str(local_root() / "models/MOFSimplify")
        )
        self.SOLVENT_THERMAL_MODEL_PATH = self.SOLVENT_THERMAL_MODELS

        self.CHROMA_KEY = os.getenv("CHROMA_KEY")

        upload = UPLOAD_CONTEXT.get()
        self.UPLOAD_FILES_TYPE = upload.get("type", "")
        self.UPLOAD_FILES_BASE_PATH = upload.get("base_path", "")
        self.UPLOAD_FILES_NAMES = upload.get("names", [])
        self.UPLOAD_FILES_PATHS = upload.get("paths", [])
