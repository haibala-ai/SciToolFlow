"""Start/inspect/stop the persistent, loopback-only Qwen vLLM service."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATE = ROOT / ".local/cache/qwen_vllm"
CONFIG = ROOT / "configs/services/qwen_vllm.json"


def birth(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] if fields[0] not in {"Z", "X"} else None
    except (OSError, IndexError):
        return None


def load_state():
    path = STATE / "service.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    return data, bool(
        data
        and data.get("process_birth")
        and birth(data["pid"]) == data["process_birth"]
    )


def health(url):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + "/health", timeout=3) as r:
            return r.status == 200
    except (OSError, urllib.error.URLError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop"])
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Keep the supervisor in the terminal or tmux pane",
    )
    parser.add_argument("--gpus", help="Comma-separated physical GPU indices, e.g. 6,7")
    parser.add_argument(
        "--python",
        dest="python_path",
        help="Interpreter in the SciTool-LLM environment",
    )
    parser.add_argument("--model-path", help="Local model directory")
    parser.add_argument("--served-model-name")
    parser.add_argument("--port", type=int)
    parser.add_argument("--gpu-memory-utilization", type=float)
    args = parser.parse_args()
    from scitoolflow.paths import load_environment
    from tools.runtime.environments import environment_python

    load_environment()
    config = json.loads(CONFIG.read_text())
    if args.gpus is not None:
        try:
            config["gpus"] = [int(value.strip()) for value in args.gpus.split(",")]
        except ValueError:
            parser.error("--gpus must contain comma-separated nonnegative indices")
    if (
        not config["gpus"]
        or len(set(config["gpus"])) != len(config["gpus"])
        or any(x < 0 for x in config["gpus"])
    ):
        parser.error("GPU indices must be nonnegative, distinct and nonempty")
    config["python"] = (
        args.python_path
        or os.getenv("SCITOOL_LLM_PYTHON")
        or str(environment_python("SciTool-LLM"))
    )
    for key in ["model_path", "served_model_name", "port", "gpu_memory_utilization"]:
        value = getattr(args, key)
        if value is not None:
            config[key] = value
    if not 0 < config["gpu_memory_utilization"] < 1:
        parser.error("GPU memory utilization must be between 0 and 1")
    STATE.mkdir(parents=True, exist_ok=True)
    state, alive = load_state()
    url = f"http://127.0.0.1:{config['port']}"
    if args.action == "status":
        ready = health(url)
        print(
            json.dumps(
                {
                    "alive": alive,
                    "ready": ready,
                    "api_base": url + "/v1",
                    "log": str(STATE / "server.log"),
                    **state,
                },
                indent=2,
            )
        )
        return 0 if alive and ready else 1
    if args.action == "stop":
        if alive:
            os.killpg(state["pid"], signal.SIGTERM)
            for _ in range(100):
                if birth(state["pid"]) != state["process_birth"]:
                    break
                time.sleep(0.2)
            else:
                os.killpg(state["pid"], signal.SIGKILL)
        (STATE / "service.json").unlink(missing_ok=True)
        print(json.dumps({"stopped": alive}))
        return 0
    if alive:
        print(
            json.dumps(
                {"already_running": True, "pid": state["pid"], "ready": health(url)}
            )
        )
        return 0
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", config["port"]))
    python = Path(config["python"])
    model = ROOT / config["model_path"]
    if not python.is_file() or not (model / "config.json").is_file():
        raise ValueError("Python/model path not found")
    reply = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.total,memory.free,pci.bus_id",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    cards = {
        int(r[0]): {
            "uuid": r[1].strip(),
            "total_mib": float(r[2]),
            "free_mib": float(r[3]),
            "pci_bus_id": r[4].strip(),
        }
        for line in reply.stdout.splitlines()
        if (r := line.split(","))
    }
    # vLLM 0.21's NVML mapping expects numeric CUDA_VISIBLE_DEVICES entries.
    # Require PCI order to agree with nvidia-smi before using those indices.
    if sorted(cards, key=lambda i: cards[i]["pci_bus_id"]) != sorted(cards):
        raise RuntimeError(
            "NVML indices differ from PCI order; explicit device mapping is required"
        )
    selected = [cards[i] for i in config["gpus"]]
    margin = float(config.get("startup_free_memory_margin_mib", 512))
    if any(
        c["free_mib"] < c["total_mib"] * config["gpu_memory_utilization"] + margin
        for c in selected
    ):
        raise RuntimeError(
            f"Insufficient free GPU memory for the configured budget plus {margin:g} MiB margin"
        )
    command = [
        str(python),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(model),
        "--served-model-name",
        config["served_model_name"],
        "--host",
        "127.0.0.1",
        "--port",
        str(config["port"]),
        "--tensor-parallel-size",
        str(len(selected)),
        "--dtype",
        "bfloat16",
        "--distributed-executor-backend",
        "mp",
        "--gpu-memory-utilization",
        str(config["gpu_memory_utilization"]),
        "--max-model-len",
        str(config["max_model_len"]),
        "--max-num-seqs",
        str(config["max_num_seqs"]),
        "--max-num-batched-tokens",
        str(config["max_num_batched_tokens"]),
        "--language-model-only",
        "--enforce-eager",
        "--disable-custom-all-reduce",
        "--reasoning-parser",
        "qwen3",
        "--default-chat-template-kwargs",
        json.dumps({"enable_thinking": False}),
    ]
    env = os.environ.copy()
    env.update(
        CUDA_VISIBLE_DEVICES=",".join(str(i) for i in config["gpus"]),
        CUDA_DEVICE_ORDER="PCI_BUS_ID",
        PYTHONNOUSERSITE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        VLLM_NO_USAGE_STATS="1",
        DO_NOT_TRACK="1",
        NCCL_P2P_DISABLE="1",
        VLLM_USE_FLASHINFER_SAMPLER="0",
        OMP_NUM_THREADS="4",
        OPENBLAS_NUM_THREADS="1",
        TOKENIZERS_PARALLELISM="false",
    )
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    # CUDA_HOME is one directory, not a colon-separated search path.
    cuda_home = env.get("CUDA_HOME", "")
    if not cuda_home or not (Path(cuda_home) / "bin/nvcc").is_file():
        if Path("/usr/local/cuda/bin/nvcc").is_file():
            env["CUDA_HOME"] = "/usr/local/cuda"
        else:
            env.pop("CUDA_HOME", None)
    env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
    # A detached process with file-backed streams survives the launching shell.
    if args.foreground:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)
    else:
        with (STATE / "server.log").open("ab", buffering=0) as log:
            proc = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
    state = {
        "pid": proc.pid,
        "process_birth": birth(proc.pid),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "physical_gpus": config["gpus"],
        "gpu_uuids": [c["uuid"] for c in selected],
        "api_base": url + "/v1",
        "command": command,
        "config": str(CONFIG),
        "effective_config": config,
    }
    (STATE / "service.json").write_text(json.dumps(state, indent=2) + "\n")
    print(
        json.dumps(
            {
                "started": True,
                "pid": proc.pid,
                "api_base": url + "/v1",
                "log": str(STATE / "server.log"),
            }
        ),
        flush=True,
    )
    if args.foreground:

        def stop_child(signum, frame):
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGTERM, stop_child)
        signal.signal(signal.SIGHUP, stop_child)
        try:
            return proc.wait()
        except KeyboardInterrupt:
            stop_child(signal.SIGINT, None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
