import logging
import os
import sys
import traceback
import math
import time
from heapq import nlargest
from logging.config import dictConfig
from typing import Callable, List, TypeVar, Dict

import torch
from celery import Celery, Task
from celery.signals import setup_logging
from rxn.chemutils.conversion import canonicalize_smiles
from rxn.chemutils.exceptions import InvalidSmiles
from prediction import forward_reaction, retro_reaction
from model_loading import load_forward_model, load_retro_model, reaction_likelihood
from spectators import is_spectator, strip_neutral_spectators
from simplicity import simplicity


# Avoid CPU over-subscription.
torch.set_num_threads(int(os.getenv("RXN_TORCH_NUM_THREADS", "1")))

logger = logging.getLogger(__name__)

app = Celery()
app.config_from_object("celeryconfig")

T = TypeVar("T")

def handle_exception(message: str) -> Dict:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    return {
        "title": f"{message}: {getattr(exc_type, '__name__', 'Exception')}",
        "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback),
        "detail": str(exc_value),
    }


@setup_logging.connect
def configure_logging(**kwargs):
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "rxn": {
                "format": "%(asctime)s %(levelname)-8s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
            }
        },
        "handlers": {
            "worker_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "worker.log",
                "formatter": "rxn",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
            },
            "celery_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "celery.log",
                "formatter": "rxn",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
            },
        },
        "loggers": {
            "celery": {"level": "DEBUG", "handlers": ["celery_file"], "propagate": False},
            "amqp": {"level": "DEBUG", "handlers": ["celery_file"], "propagate": False},
            "kombu": {"level": "DEBUG", "handlers": ["celery_file"], "propagate": False},
            "": {"level": "INFO", "handlers": ["worker_file"]},
        },
    })


def run_task(task: Task, name: str, fn: Callable[[], T]) -> T:
    """
    Wraps the running and error handling of a celery task.
    """
    logger.info("Starting %s", name)

    started = time.time()
    task.update_state(state="STARTED")
    try:
        result = fn()
        finished = time.time()
        return {
            "result": result,
            "time": finished - started,
        }
    except Exception as exception:
        logger.exception("Error in %s", name)
        raise


@app.task(bind=True)
def product_prediction(self: Task, reactants_list: List[str], **kwargs):
    def callback():
        return product_prediction_body(reactants_list, **kwargs)

    return run_task(task=self, name="product_prediction", fn=callback)


def product_prediction_body(reactants_list: List[str], **kwargs):
    logger.info("product_prediction: reactants_list=%s, kwargs=%s", reactants_list, kwargs)

    # Checkpoint and vocab for the forward model. Should use the included one.
    ckpt_forward = kwargs.get("ckpt_forward", "Pistachio2025Q2-Forward")
    ckpt_forward_path = kwargs.get("ckpt_forward_path", f"models/forward/{ckpt_forward}.ckpt")
    vocab = kwargs.get("vocab", "Pistachio2025Q2")
    vocab_path = kwargs.get("vocab_path", f"vocab/{vocab}.txt")
    # Forward algorithm parameters
    nbeams = kwargs.get("num_beams", 3)
    topn = kwargs.get("topn", 1)
    # Device used for predicting, defaults to "cuda" if available
    device = kwargs.get("device", None)

    # Forward model used for product predictions
    forward_lit = load_forward_model(
        ckpt_path=ckpt_forward_path,
        vocab_path=vocab_path,
        num_beams=nbeams,
        topn=topn,
        device=device,
    )

    # Return the prediction results for a batch of product predictions
    return forward_reaction(
        smiles_list=reactants_list,
        lit=forward_lit,
    )


@app.task(bind=True)
def retro_prediction(self: Task, product: str, **kwargs):
    def callback():
        return retro_prediction_body(product, **kwargs)

    return run_task(task=self, name="retro_prediction", fn=callback)


def retro_prediction_body(product: str, **kwargs):
    logger.info("retro_prediction: product=%s, kwargs=%s", product, kwargs)

    # Checkpoints to the retrosynthesis and forward models. Should use the included models.
    ckpt_retro = kwargs.get("ckpt_retro", "Pistachio2025Q2-Retro")
    ckpt_retro_path = kwargs.get("ckpt_retro_path", f"models/retrosynthesis/{ckpt_retro}.ckpt")
    ckpt_forward = kwargs.get("ckpt_forward", "Pistachio2025Q2-Forward")
    ckpt_forward_path = kwargs.get("ckpt_forward_path", f"models/forward/{ckpt_forward}.ckpt")
    # Vocab path for the retrosynthesis and forward models. For the defaults models the vocab is the same.
    vocab = kwargs.get("vocab", "Pistachio2025Q2")
    vocab_path = kwargs.get("vocab_path", f"vocab/{vocab}.txt")
    # Retrosynthesis algorithm parameters
    topn = kwargs.get("topn", 15)   # Number of retro prediction results per product SMILES
    fap = kwargs.get("fap", 0.6)    # Forward likelihood acceptance probability (not length averaged)
    fld = kwargs.get("dfl", 0.2)    # Forward likelihood delta between the top2 forward prediction results
    nbeams = max(kwargs.get("num_beams", 15), topn) # Must never be lower than topn
    # Device used for predicting, defaults to "cuda" if available
    device = kwargs.get("device", None)


    # Retro model used for retrosynthesis prediction
    retro_lit = load_retro_model(
        ckpt_path=ckpt_retro_path,
        vocab_path=vocab_path,
        num_beams=nbeams,
        topn=topn,
        device=device,
    )

    # Forward model used to get the forward likelihood and top‑2 forward prediction with the predicted reactants
    forward_lit = load_forward_model(
        ckpt_path=ckpt_forward_path,
        vocab_path=vocab_path,
        num_beams=2,
        topn=2,
        device=device,
    )

    # Return the prediction results for a single retrosynthesis step
    return retro_single_step(
        product=product,
        retro_lit=retro_lit,
        forward_lit=forward_lit,
        fap=fap,
        fld=fld,
    )


# Predicts the retrosynthesis reaction for a given product
def retro_single_step(
    product: str,
    retro_lit,
    forward_lit,
    fap: float = 0.6,
    fld: float = 0.2,
):
    # Canonicalize the product before doing retrosynthesis
    product = canonicalize_smiles(product)

    # Get retrosynthesis prediction results
    retro_results = retro_reaction(
        smiles=product,
        lit=retro_lit,
    )

    # Empty list for accepted results
    accepted_results = []

    # Loop retro prediction results
    for result in retro_results:

        logger.info("Evaluating retro result: %s", result)

        # Get the predicted reactants
        reactants = result.get("reactants")

        # Step 1: Canonicalize reactants
        # If it fails to canonicalize -> skips to next result
        try:
            reactants = canonicalize_smiles(reactants)
        except InvalidSmiles as e:
            logger.info("Invalid SMILES '%s': %s", reactants, e)
            continue

        # Step 2: Skips to next result if product is among the reactants
        if product in reactants.split("."):
            logger.info("Product appears among reactants, skipping.")
            continue

        # Step 3: Compute forward likelihood
        likelihood = reaction_likelihood(forward_lit, reactants, product)

        # Step 4: Results with strong likelihood (above the fap that was set) are added to the accepted results list
        if likelihood > fap:
            accepted_results.append(result)
            continue

        # Step 5: Generate top‑2 forward predictions
        forward_preds = forward_reaction(
            smiles_list=[reactants],
            lit=forward_lit,
        )

        # If it wasn't able to generate the 2 results, it skips to the next result
        if len(forward_preds) < 2:
            continue

        top1, top2 = forward_preds[0], forward_preds[1]

        # Step 6: The top‑1 prediction must match target product
        if top1["product"] != product:
            continue

        # Step 7: The different between the top1 and top2 likelihood bust be higher than fld to accept the result
        likelihood_top1 = reaction_likelihood(forward_lit, reactants, top1["product"])
        likelihood_top2 = reaction_likelihood(forward_lit, reactants, top2["product"])
        if likelihood_top1 > likelihood_top2 + fld:
            accepted_results.append(result)

    # Return the accepted results
    return accepted_results


@app.task(bind=True)
def retro_prediction_tree(self: Task, product: str, **kwargs):
    def callback():
        return retro_prediction_tree_body(product, **kwargs)

    return run_task(task=self, name="retro_prediction_tree", fn=callback)


def retro_prediction_tree_body(product: str, **kwargs):
    logger.info("retro_prediction_tree: product=%s, kwargs=%s", product, kwargs)

    # Checkpoints to the retrosynthesis and forward models. Should use the included models.
    ckpt_retro = kwargs.get("ckpt_retro", "Pistachio2025Q2-Retro")
    ckpt_retro_path = kwargs.get("ckpt_retro_path", f"models/retrosynthesis/{ckpt_retro}.ckpt")
    ckpt_forward = kwargs.get("ckpt_forward", "Pistachio2025Q2-Forward")
    ckpt_forward_path = kwargs.get("ckpt_forward_path", f"models/forward/{ckpt_forward}.ckpt")
    # Vocab path for the retrosynthesis and forward models. For the defaults models the vocab is the same.
    vocab = kwargs.get("vocab", "Pistachio2025Q2")
    vocab_path = kwargs.get("vocab_path", f"vocab/{vocab}.txt")
    # Retrosynthesis algorithm parameters
    topn = kwargs.get("topn", 15)   # Number of retro prediction results per product SMILES
    fap = kwargs.get("fap", 0.6)    # Forward likelihood acceptance probability (not length averaged)
    fld = kwargs.get("dfl", 0.2)    # Forward likelihood delta between the top2 forward prediction results
    nbeams = max(kwargs.get("num_beams", 15), topn) # Must never be lower than topn
    # Retrosynthesis tree beam search parameters
    max_depth = kwargs.get("max_depth", 3)  # This is the max depth of the retrosynthesis tree
    beam_width = kwargs.get("beam_width", 5) # This is the max amount of nodes being expanded in each step
    # Device used for predicting, defaults to "cuda" if available
    device = kwargs.get("device", None)

    # Retro model used for retrosynthesis prediction
    retro_lit = load_retro_model(
        ckpt_path=ckpt_retro_path,
        vocab_path=vocab_path,
        num_beams=nbeams,
        topn=topn,
        device=device,
    )

    # Forward model used to get the forward likelihood and top‑2 forward prediction with the predicted reactants
    forward_lit = load_forward_model(
        ckpt_path=ckpt_forward_path,
        vocab_path=vocab_path,
        num_beams=2,
        topn=2,
        device=device,
    )

    # Return a retrosynthesis tree using a custom beam search algorithm and retro predictions
    return retrosynthesis_beam_search(
        product=product,
        retro_lit=retro_lit,
        forward_lit=forward_lit,
        max_steps=max_depth,
        beam_width=beam_width,
        fap=fap,
        fld=fld,
    )


def retrosynthesis_beam_search(
    product: str,
    retro_lit,
    forward_lit,
    beam_width: int = 5,    # The node limit for expansion each step
    max_steps: int = 5,     # The maximum depth of the retrosynthesis tree
    fap: float = 0.6,
    fld: float = 0.2,
    is_available_fn=None,   # Availability function can be added (future-proofing)
):
    # Canonicalize product smiles
    product = canonicalize_smiles(product)

    # List of beam paths to expand
    # We start with a single node witch corresponds to the product from where all retrosynthesis predictions start from
    beams = [{
        "open_nodes": {product},    # The product is the only node molecule at the start
        "arcs": [],                 # Arcs are the list of reactions. No arcs yet since there aren't any predictions yet
        "score": 0.0,               # Sum of all arc log scores. Starts with zero
        "expanded": set(),          # Molecule nodes already expanded. None yet
        "steps": 0,                 # Current step. Starts at step 0, can go until max_steps/max_depth
    }]

    # List of completed beam paths
    completed = []

    # Loop max_steps/max_depth
    for _ in range(max_steps):

        # New beam path candidates
        candidates = []

        # Loop paths in the list of beam paths to expand
        for path in beams:

            # If a function to check the commercial availability of the molecules exists then check if all molecules
            # in the list of nodes are available. If everything is available the beam path stops here as there is no
            # need to expand anything further
            if is_available_fn and all(is_available_fn(m) for m in path["open_nodes"]):
                completed.append(path)
                continue

            # Creates a list of expandable nodes. The expandable nodes are the molecules that weren't expanded already
            # and that are not solvents. They also need to follow the active branch path.
            # On the first iteration the product is the only expandable node
            expandable = [
                m for m in path["open_nodes"]
                if m not in path["expanded"] and not is_spectator(m)
                and ("active_branch" not in path or m in path["active_branch"])
            ]

            # If there's nothing to expand, then the beam path is complete and is added to the completed beam paths list
            if not expandable:
                completed.append(path)
                continue

            # Get the higher complexity molecule from the expandable nodes
            scores = {m: simplicity(m) for m in expandable}
            molecule = min(scores, key=scores.get)

            # Expand the molecule (retrosynthesis prediction)
            expansions = expand_molecule(
                molecule,
                retro_lit=retro_lit,
                forward_lit=forward_lit,
                fap=fap,
                fld=fld,
            )

            # If there were no retrosynthesis prediction results, then the beam can't be expanded any further
            # The beam path is added to the completed beam paths list, and it skips to the next beam path
            if not expansions:
                completed.append(path)
                continue

            # Loop the retrosynthesis prediction results (arcs) from the expansion
            for arc in expansions:

                # Cycle detection
                # If any predicted reactant matches the original product or a molecule, then
                # there is a loop and the arc is ignored
                if any(r == product for r in arc["reactants"]):
                    continue

                # Create a new beam path candidate
                new_path = {
                    # The new beam open nodes are the previous open nodes minus the molecule that was expanded
                    # The molecule removed is replaced by the reactants resultant from the retrosynthesis prediction
                    "open_nodes": (path["open_nodes"] - {molecule}) | set(arc["reactants"]),
                    # The arcs are the reactions that make the beam path
                    # Here we update it adding the new reaction
                    "arcs": path["arcs"] + [{**arc}],
                    # The beam score is the sum of all the arc log scores, here it sums the existing score with the
                    # arc log score with 1e-12 serving as log-flooring to prevent errors if the score is zero
                    "score": path["score"] + math.log(arc["arc_score"] + 1e-12),
                    # The expanded molecule is added to the expanded list
                    "expanded": path["expanded"] | {molecule},
                    # The step is incremented to keep track on how deep in the tree it currently is
                    "steps": path["steps"] + 1,
                    # Makes the retrosynthesis tree go down in a single branch instead of multiple
                    # Only do retrosynthesis on latest iteration reactants
                    "active_branch": set(arc["reactants"]),
                }

                # The new beam path is added to the list of candidates
                candidates.append(new_path)

        # If there are no new candidates the beam search is over
        if not candidates:
            break

        # Only keep unique candidates by checkin the route signature
        # If there is a duplicate, keep the one with the highest score
        unique = {}
        for candidate in candidates:
            sig = route_signature(candidate)
            if sig not in unique or candidate["score"] > unique[sig]["score"]:
                unique[sig] = candidate

        # Keep only the best beam_width results for next expansion loop or to add to the final results if on last loop
        beams = nlargest(
            beam_width,
            unique.values(),
            key=lambda p: p["score"]
        )

    # Add remaining beams to the completed beam paths list
    completed.extend(beams)

    # Only keep unique candidates by checkin the route signature
    # If there is a duplicate, keep the one with the highest score
    # We deduplicate again here since it could reach the same routes in different ways
    unique = {}
    for p in completed:
        sig = route_signature(p)
        if sig not in unique or p["score"] > unique[sig]["score"]:
            unique[sig] = p

    # Update the completed list with only the unique values
    completed = list(unique.values())

    # Return the beam search retrosynthesis tree from all the predictions
    return [
        # The results are serialized before being returned
        # All sets are converted to lists and the log sum is converted to a probability score
        serialize_pathway(p)
        # The final completed beam paths are sorted from highest to lowest score
        for p in sorted(completed, key=lambda p: p["score"], reverse=True)
    ]


# Expands a beam path by doing retrosynthesis on a molecule
def expand_molecule(
    product: str,   # Molecule to expand (retrosynthesis)
    retro_lit,      # Retrosynthesis model
    forward_lit,    # Forward model
    fap: float,     # Forward likelihood acceptance probability (not length averaged)
    fld: float,     # Forward likelihood delta between the top2 forward prediction results
):
    """
    Generate solvent-agnostic retrosynthetic steps for a product.
    Reactions differing only by solvents are deduplicated, keeping
    the highest-scoring representative.
    """

    # Single step retro prediction
    retro_predictions = retro_single_step(
        product=product,
        retro_lit=retro_lit,
        forward_lit=forward_lit,
        fap=fap,
        fld=fld,
    )

    # Product simplicity score
    sc = simplicity(product)

    # Hold the unique reactions after deduplication
    unique = {}

    # Loop prediction results from retrosynthesis
    for prediction in retro_predictions:

        # Canonicalize reactants
        reactants = canonicalize_smiles(prediction["reactants"]).split(".")
        reactants_smiles = ".".join(reactants)

        # Get forward likelihood
        p = reaction_likelihood(forward_lit, reactants_smiles, product)

        # Reactants simplicity score
        sr = 1.0
        for r in reactants:
            sr *= simplicity(r)

        # Score of the overall retro prediction
        arc_score = p * (sr / sc)

        # Create the object for this arc candidate (retrosynthesis reaction)
        candidate = {
            "product": product,
            "reactants": reactants,
            "forward_likelihood": p,
            "arc_score": arc_score,
            "confidence": prediction.get("confidence"),
            "metadata": prediction,
        }

        # Only keep unique candidates by checkin the reaction signature
        # If there is a duplicate, keep the one with the highest score
        # We strip the solvents on the reaction signature so that they don't influence the reactions uniqueness
        sig = reaction_signature(product, reactants)
        if sig not in unique or arc_score > unique[sig]["arc_score"]:
            unique[sig] = candidate

    # Return the list of unique reaction
    return list(unique.values())


# Serializes the beam paths so they can be properly sent via the celery worker
def serialize_pathway(path):
    return {
        "open_nodes": list(path["open_nodes"]),
        "expanded": list(path["expanded"]),
        "score": math.exp(path["score"]),   # Converted to probability
        "steps": path["steps"],
        "arcs": path["arcs"],
    }

# Route signature function to ensure all routes are unique
def route_signature(path):
    """
    Canonical, hashable signature of a retrosynthesis route.
    """
    # This will return a route signature with the following format:
    # (
    #     (
    #         "<original-product>",
    #         ("<depth0-reactant1>", "<depth0-reactant2>", ..., "<depth0-reactantN>")
    #     ),
    #     (
    #         "<depth0-reactant-expanded>",
    #         ("<depth1-reactant1>", "<depth1-reactant2>", ..., "<depth1-reactantN>")
    #     ),
    #     ...
    # )
    return tuple(
        (arc["product"], tuple(sorted(arc["reactants"])))
        for arc in path["arcs"]
    )

# Route signature function to ensure all reactions are unique
# We remove the solvents before creating a signature since their presence does not equate to a different reaction
def reaction_signature(product, reactants):
    """
    Canonical representation of a reaction ignoring solvents.
    """
    # This will return a route signature with the following format:
    # (
    #     "<product>",
    #     ("<reactant1>", "<reactant2>", ..., "<reactantN>")
    # )
    core_reactants = tuple(strip_neutral_spectators(reactants))
    return product, core_reactants
