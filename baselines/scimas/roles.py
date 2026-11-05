"""Independent role contexts with one shared generation ledger and durable requests."""

from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from baselines.common.resources import BudgetedClient, ResourceLimit
from tools.runtime.contracts import contract_errors
from .schema import decoding_schema


class RecordedClient(BudgetedClient):
    def __init__(self, client, resources, phase, trace, save, max_decisions=None):
        super().__init__(client, resources, phase)
        self.trace, self.save, self.max_decisions = trace, save, max_decisions

    def request(self, messages, **kwargs):
        if (
            self.max_decisions is not None
            and len(self.resources.requests) >= self.max_decisions
        ):
            raise ResourceLimit("DecisionBudget")
        self.resources.check()
        step = {
            "type": "decision",
            "role": self.phase,
            "model": {"messages": deepcopy(messages), "response": None},
        }
        self.trace["steps"].append(step)
        self.save()
        try:
            reply = super().request(messages, **kwargs)
            step["model"]["response"] = deepcopy(reply)
            return reply
        except Exception as error:
            step["model"]["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            self.save()


class Roles:
    def __init__(
        self,
        client_factory,
        *,
        max_tokens,
        max_chars,
        retries=3,
        schema_guard=True,
        on_protocol_error=None,
    ):
        self.client_factory, self.max_tokens, self.max_chars = (
            client_factory,
            max_tokens,
            max_chars,
        )
        self.retries, self.schema_guard = retries, schema_guard
        self.on_protocol_error = on_protocol_error

    def ask(self, role, payload, schema):
        client = self.client_factory(role)
        prompt = (Path(__file__).parent / "prompts" / (role + ".md")).read_text()
        feedback = None
        for _ in range(self.retries):
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "context": payload,
                            "response_schema": schema,
                            "format_feedback": feedback,
                        },
                        ensure_ascii=False,
                        allow_nan=False,
                    ),
                },
            ]
            if sum(len(m["content"]) for m in messages) > self.max_chars:
                raise ValueError(
                    "Role context too large; narrow the plan or inspect smaller evidence fields"
                )
            if getattr(client, "backend", None) == "vllm":
                if client.count_tokens(messages) > client.input_budget(self.max_tokens):
                    raise ValueError("Role context exceeds model input capacity")
            options = (
                {"response_schema": decoding_schema(schema)}
                if self.schema_guard
                and getattr(client, "supports_response_schema", False)
                else {}
            )
            scope = (
                client.generation_scope()
                if hasattr(client, "generation_scope")
                else nullcontext()
            )
            with scope:
                reply = client.request(messages, max_tokens=self.max_tokens, **options)
            text = reply["text"].strip()
            if text.startswith("```json") and text.endswith("```"):
                text = text[7:-3].strip()
            try:
                value = json.loads(text)
                errors = contract_errors(value, schema)
            except (ValueError, TypeError) as error:
                errors = [str(error)]
            if not errors:
                return value
            if self.on_protocol_error is not None:
                self.on_protocol_error(errors)
            feedback = {"errors": errors, "previous_response": text}
        raise ValueError(
            "Role protocol retry limit reached: " + str(feedback["errors"])
        )
