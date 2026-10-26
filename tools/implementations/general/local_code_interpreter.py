"""Bounded numerical Python, with optional model-assisted code generation."""

from src.utils.paths import local_root, artifacts_root
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
import time

ROOT = local_root()
IMPORTS = {"math", "statistics", "numpy", "matplotlib.pyplot"}
BUILTINS = {
    "print",
    "sum",
    "len",
    "range",
    "min",
    "max",
    "sorted",
    "enumerate",
    "zip",
    "float",
    "int",
    "str",
    "list",
    "dict",
    "tuple",
    "set",
    "abs",
    "round",
    "pow",
    "all",
    "any",
    "bool",
}
ATTRIBUTES = set(
    "pi e tau inf nan sqrt exp log log10 log2 sin cos tan asin acos atan atan2 floor ceil factorial "
    "mean median stdev pstdev variance pvariance array arange linspace zeros ones std var sum prod "
    "abs round min max argmin argmax percentile quantile dot matmul transpose reshape ravel flatten "
    "tolist item shape size ndim column_stack concatenate stack isfinite isclose allclose cumsum diff "
    "where sort argsort polyfit polyval histogram corrcoef cov figure subplots plot scatter bar hist "
    "xlabel ylabel title legend grid tight_layout savefig close set_title set_xlabel set_ylabel "
    "set_xlim set_ylim set xticks yticks".split()
)


def validate(code):
    tree = ast.parse(code)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    if len(code) > 12000 or len(list(ast.walk(tree))) > 2000:
        raise ValueError("Code exceeds the bounded numerical interpreter contract")
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Lambda,
                ast.With,
                ast.AsyncWith,
                ast.Global,
                ast.Nonlocal,
                ast.Try,
                ast.Raise,
                ast.Delete,
            ),
        ):
            raise ValueError(
                "Only numerical expressions, assignments, loops and plotting are supported"
            )
        if isinstance(node, ast.Name) and (
            node.id.startswith("_")
            or node.id
            in {
                "open",
                "exec",
                "eval",
                "compile",
                "getattr",
                "setattr",
                "globals",
                "locals",
                "vars",
                "__import__",
                "input",
            }
        ):
            raise ValueError("Name outside the numerical interpreter contract")
        if isinstance(node, ast.Import):
            if any(alias.name not in IMPORTS for alias in node.names):
                raise ValueError(
                    "Imports limited to math, statistics, numpy and matplotlib.pyplot"
                )
        if isinstance(node, ast.ImportFrom):
            if (
                node.level
                or node.module not in IMPORTS
                or any(
                    alias.name not in ATTRIBUTES or alias.name == "savefig"
                    for alias in node.names
                )
            ):
                raise ValueError("Unsupported module/member import")
        if isinstance(node, ast.Attribute) and node.attr not in ATTRIBUTES:
            raise ValueError("Unsupported attribute: " + node.attr)
        if isinstance(node, ast.Attribute) and node.attr == "savefig":
            parent = parents.get(node)
            if not isinstance(parent, ast.Call) or parent.func is not node:
                raise ValueError(
                    "savefig may only be called directly with a checked literal filename"
                )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "savefig"
        ):
            if (
                not node.args
                or not isinstance(node.args[0], ast.Constant)
                or not isinstance(node.args[0].value, str)
            ):
                raise ValueError("savefig requires a literal image filename")
            name = node.args[0].value
            if not re.fullmatch(r"[A-Za-z0-9_-]+\.(png|svg|pdf)", name):
                raise ValueError("Plot filename must be a simple local basename")
    return tree


def numerical_contract():
    """Public language limits, generated from the actual runtime allowlists."""
    return {
        'imports': sorted(IMPORTS), 'builtins': sorted(BUILTINS),
        'attributes': sorted(ATTRIBUTES), 'source_characters_max': 12000,
        'AST_nodes_max': 2000, 'CPU_seconds': 10, 'address_space_GiB': 4,
        'bytes_per_file_max': 2*1024**2, 'wall_seconds_max': 20,
        'syntax': 'Numerical expressions, assignments, indexing, comprehensions, conditionals and loops. No custom functions/classes/lambda, with/try/raise, private names, filesystem/network/shell or dynamic execution. Attributes are an exhaustive allowlist and still require a compatible object. from-import members must be on that list and cannot import savefig.',
        'plot_filenames': 'Call savefig directly with a literal simple local basename ending in .png, .svg or .pdf.',
        'unsupported_examples': ['np.linalg', 'np.roots', 'np.eye', 'array.T', 'list.append'],
        'alternatives': 'Use registered typed tools for linear systems, eigen/SVD, polynomial roots and normal CDF. Print numerical results explicitly; .tolist() gives JSON-shaped containers.',
        'initialization': 'Trusted bootstrap initializes NumPy reductions and representations before actor execution. Actor imports and language permissions remain restricted.',
    }


def _warm_numpy():
    """Initialize internal lazy imports before restricting the actor namespace."""
    import numpy as np
    for name in ('sum', 'prod', 'mean', 'std', 'var', 'min', 'max', 'argmin',
                 'argmax', 'cumsum', 'sort'):
        getattr(np.array([1., 2., 3.]), name)()
    str(np.array([1., 2.]))
    repr(np.array([1., 2.]))


def execute_child(code):
    import builtins
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
    tree = validate(code)
    _warm_numpy()

    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name not in IMPORTS or level:
            raise ImportError("Unsupported numerical module")
        return builtins.__import__(name, globals, locals, fromlist, level)

    namespace = {"__builtins__": {name: getattr(builtins, name) for name in BUILTINS}}
    namespace["__builtins__"]["__import__"] = restricted_import
    exec(compile(tree, "generated_numerical_code.py", "exec"), namespace)


def interpret_question(question: str):
    """Local official Qwen generates and executes restricted numerical/plotting Python; no arbitrary filesystem, network or shell operations."""
    from src.models.local import RUNTIME
    from src.models.trace import record

    prompt = (
        "Write only Python code for the numerical request below. Use print for results. "
        "Allowed imports: math, statistics, numpy as np, matplotlib.pyplot as plt. "
        "No filesystem reads, network, shell commands, exec/eval, classes, custom functions or private attributes. "
        "For plots use plt.savefig('result.png'). Do not use pandas or external data. "
        "If the request needs unavailable data or operations, print a precise limitation.\nRequest: "
        + question
    )
    reply = RUNTIME.request("chat", messages=[{"role": "user", "content": prompt}])
    code = reply["text"].strip()
    match = re.fullmatch(r"```(?:python)?\s*\n(.*?)\n```", code, re.DOTALL)
    if match:
        code = match[1]
    validate(code)
    directory = artifacts_root() / ("code_interpreter_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    (directory / "generated_code.py").write_text(code)
    env = os.environ.copy()
    env.update(
        MPLBACKEND="Agg",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
    )
    with (directory / "stdout.txt").open("w") as out, (directory / "stderr.txt").open(
        "w"
    ) as err:
        from tools.runtime.context import TOOL_DEADLINE

        deadline = TOOL_DEADLINE.get()
        remaining = 20 if deadline is None else min(20, deadline - time.monotonic())
        if remaining <= 0:
            raise TimeoutError("Numerical execution exceeded the tool deadline")
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve())],
            input=json.dumps({"code": code}),
            text=True,
            stdout=out,
            stderr=err,
            cwd=directory,
            env=env,
            timeout=remaining,
        )
    stdout = (directory / "stdout.txt").read_text()
    record(
        "llm_call",
        model=reply["model"],
        operation="local_code_interpreter",
        question=question,
        response=reply["text"],
        duration_seconds=reply["duration_seconds"],
        usage=reply.get("usage"),
    )
    if completed.returncode:
        raise RuntimeError(
            "Generated numerical code failed; execution diagnostics: " + str(directory)
        )
    return json.dumps(
        {
            "source": "local Qwen plus bounded numerical Python execution",
            "model": "Qwen/Qwen3.5-9B",
            "question": question,
            "generated_code": code,
            "stdout": stdout[:125000],
            "stdout_truncated": len(stdout) > 125000,
            "artifact_directory": str(directory),
            "plots": [
                str(p)
                for p in sorted(directory.iterdir())
                if p.suffix in [".png", ".svg", ".pdf"]
            ],
            "scope": "restricted numerical calculations and plots; no arbitrary code/I-O/network execution",
        }
    )


if __name__ == "__main__":
    execute_child(json.load(sys.stdin)["code"])


def execute_numerical_code(code: str) -> dict:
    """Execute caller-authored bounded numerical Python without an inner LLM.

    Accept at most12000 code characters/2000 AST nodes; math/statistics/numpy/
    matplotlib numerical imports only. No filesystem reads, networking, shell,
    custom functions/classes or private attributes. Print values explicitly;
    plots may use literal local basenames. A fresh child has10 CPU seconds,
    4GiB address space and2MiB/file limits. Artifacts stay in an explicit
    task-local directory; return code/stdout/stderr/plots, never hidden reasoning.
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError('code must be a nonempty Python source string')
    validate(code)
    from tools.implementations.general.research_data import _task_artifacts_root
    directory = _task_artifacts_root() / ('numerical_code_' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    (directory / 'code.py').write_text(code)
    env = os.environ.copy()
    env.update(MPLBACKEND='Agg', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    from tools.runtime.context import TOOL_DEADLINE
    deadline = TOOL_DEADLINE.get()
    remaining = 20 if deadline is None else min(20, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError('Numerical execution exceeded tool deadline')
    with (directory / 'stdout.txt').open('w') as out, (directory / 'stderr.txt').open('w') as err:
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve())], input=json.dumps({'code': code}), text=True, stdout=out, stderr=err, cwd=directory, env=env, timeout=remaining)
    stdout = (directory / 'stdout.txt').read_text()
    stderr = (directory / 'stderr.txt').read_text()
    return dict(status='success' if completed.returncode == 0 else 'error', error=None if completed.returncode == 0 else 'Numerical code failed; inspect stderr for the execution error.', exit_code=completed.returncode, execution_status='completed' if completed.returncode == 0 else 'failed', code=code, stdout=stdout[:125000], stdout_truncated=len(stdout)>125000, stderr=stderr[-16000:], stderr_truncated=len(stderr)>16000, artifact_directory=str(directory), plots=[str(p) for p in sorted(directory.iterdir()) if p.suffix in {'.png', '.svg', '.pdf'}], scope='Caller-authored bounded numerical execution; no internal LLM call, data acquisition or inferred scientific interpretation')
