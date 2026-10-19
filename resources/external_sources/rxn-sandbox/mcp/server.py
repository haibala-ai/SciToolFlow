import os
import asyncio
from typing import Optional
from mcp.server.fastmcp import FastMCP
from celery import Celery
from celery.exceptions import TimeoutError


CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "amqp://ubuntu:ubuntu@broker:5672//")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://:ubuntu@redis:6379/0")

app = Celery("mcp-client", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

mcp = FastMCP("rxn-mcp-server", json_response=False)


async def wait_for_celery_result(task, timeout: int = 300):
    def _get():
        return task.get(timeout=timeout)

    return await asyncio.to_thread(_get)


@mcp.tool()
async def product_prediction(
        reactants_list: list[str],
        topn: int = 3,
        num_beams: int = 3,
        device: Optional[str] = None,
        ckpt_forward = "Pistachio2025Q2-Forward",
        vocab = "Pistachio2025Q2",
):
    """
    Gets the product prediction for a batch of reactants SMILES.

    Args:
        reactants_list (list[str]): List of reactants SMILES.
        topn (int): number of predictions per reactant (Defaults to 3).
        num_beams (int): beams used for prediction (num_beams >= topn) (Defaults to 3).
        device (Optional str): device used for predicting, either "cuda" or "cpu", None defaults to cuda if available.
        ckpt_forward (Optional str): name of the forward model without extension. Should exist inside the "models/forward" directory and be a .ckpt file.
        vocab (Optional str): name of the vocab file without extension. Should exist inside the "vocab" directory and be a .txt file.
    """
    try:
        kwargs = {
            "topn": topn,
            "num_beams": num_beams,
            "device": device,
            "ckpt_forward": ckpt_forward,
            "vocab": vocab,
        }
        task = app.send_task(
            "tasks.product_prediction",
            [reactants_list],
            kwargs=kwargs,
            queue="product_prediction",
        )
        result = await wait_for_celery_result(task, timeout=600)
        result["status"] = "success"
        return result
    except TimeoutError:
        return {
            "status": "timeout",
            "message": "Computation exceeded time limit",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@mcp.tool()
async def retro_prediction(
        product: str,
        topn: int = 15,
        num_beams: int = 15,
        fap: float = 0.6,
        fld: float = 0.2,
        device: Optional[str] = None,
        ckpt_forward = "Pistachio2025Q2-Forward",
        ckpt_retro = "Pistachio2025Q2-Retro",
        vocab = "Pistachio2025Q2",
):
    """
    Gets the retrosynthesis prediction for a product SMILES.

    Args:
        product (str): List of reactants SMILES.
        topn (int): number of retrosynthesis predictions (Defaults to 15).
        num_beams (int): beams used for prediction (num_beams >= topn) (Defaults to 15).
        fap (float): forward acceptance level (Defaults to 0.6).
        fld (float): forward likelihood delta (Defaults to 0.2).
        device (Optional str): device used for predicting, either "cuda" or "cpu", None defaults to cuda if available.
        ckpt_forward (Optional str): name of the forward model without extension. Should exist inside the "models/forward" directory and be a .ckpt file.
        ckpt_retro (Optional str): name of the retrosynthesis model without extension. Should exist inside the "models/retrosynthesis" directory and be a .ckpt file.
        vocab (Optional str): name of the vocab file without extension. Should exist inside the "vocab" directory and be a .txt file.
    """
    try:
        kwargs = {
            "topn": topn,
            "num_beams": num_beams,
            "fap": fap,
            "fld": fld,
            "device": device,
            "ckpt_forward": ckpt_forward,
            "ckpt_retro": ckpt_retro,
            "vocab": vocab,
        }
        task = app.send_task(
            "tasks.retro_prediction",
            [product],
            kwargs=kwargs,
            queue="retro_prediction",
        )
        result = await wait_for_celery_result(task, timeout=600)
        result["status"] = "success"
        return result
    except TimeoutError:
        return {
            "status": "timeout",
            "message": "Computation exceeded time limit",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@mcp.tool()
async def retro_tree_prediction(
        product: str,
        topn: int = 15,
        num_beams: int = 15,
        fap: float = 0.6,
        fld: float = 0.2,
        max_depth: int = 3,
        beam_width: int = 5,
        device: Optional[str] = None,
        ckpt_forward = "Pistachio2025Q2-Forward",
        ckpt_retro = "Pistachio2025Q2-Retro",
        vocab = "Pistachio2025Q2",
):
    """
    Gets the full retrosynthesis tree for a product SMILES.

    Args:
        product (str): List of reactants SMILES.
        topn (int): number of retrosynthesis predictions (Defaults to 15).
        num_beams (int): beams used for prediction (num_beams >= topn) (Defaults to 15).
        fap (float): forward acceptance level (Defaults to 0.6).
        fld (float): forward likelihood delta (Defaults to 0.2).
        max_depth (int): maximum number of retrosynthesis expansions in the tree (Defaults to 3).
        beam_width (int): number of molecules chosen for expansion in each step of the tree (Defaults to 5).
        device (Optional str): device used for predicting, either "cuda" or "cpu", None defaults to cuda if available.
        ckpt_forward (Optional str): name of the forward model without extension. Should exist inside the "models/forward" directory and be a .ckpt file.
        ckpt_retro (Optional str): name of the retrosynthesis model without extension. Should exist inside the "models/retrosynthesis" directory and be a .ckpt file.
        vocab (Optional str): name of the vocab file without extension. Should exist inside the "vocab" directory and be a .txt file.
    """
    try:
        kwargs = {
            "topn": topn,
            "num_beams": num_beams,
            "fap": fap,
            "fld": fld,
            "max_depth": max_depth,
            "beam_width": beam_width,
            "device": device,
            "ckpt_forward": ckpt_forward,
            "ckpt_retro": ckpt_retro,
            "vocab": vocab,
        }
        task = app.send_task(
            "tasks.retro_prediction_tree",
            [product],
            kwargs=kwargs,
            queue="retro_prediction",
        )
        result = await wait_for_celery_result(task, 1500)
        result["status"] = "success"
        return result
    except TimeoutError:
        return {
            "status": "timeout",
            "message": "Computation exceeded time limit",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


if __name__ == "__main__":
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8001
    asyncio.run(mcp.run_streamable_http_async())
