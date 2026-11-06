"""Configure generation API credentials through a hidden local terminal prompt."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from dotenv import dotenv_values, set_key
from src.utils.paths import project_root


def save_settings(path, values):
    """Atomically update dotenv keys while preserving other service credentials."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("Credential file must not be a symlink")
    descriptor, name = tempfile.mkstemp(prefix=".api-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            if path.exists():
                stream.write(path.read_text(encoding="utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        for key, value in values.items():
            set_key(temporary, key, value, quote_mode="always")
        os.chmod(temporary, 0o600)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def hidden_key():
    # Refuse redirected input: getpass otherwise falls back to potentially echoed
    # stdin in terminals without echo control. The key never becomes a CLI arg.
    if not sys.stdin.isatty():
        raise ValueError(
            "Run this command in an interactive terminal for hidden key input"
        )
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        key = getpass.getpass("Generation API key (hidden): ")
    if not key or key != key.strip() or any(c.isspace() for c in key):
        raise ValueError("API key must be nonempty and contain no whitespace")
    return key


def use_profile(name):
    """Activate a saved local generation profile without replacing other services."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Generation API profile name is invalid")
    folder = project_root() / ".local/credentials"
    source = folder / "api" / (name + ".env")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Generation API profile is missing or is a symlink")
    values = dotenv_values(source)
    required = {"SCITOOLFLOW_API_BASE", "SCITOOLFLOW_API_MODEL", "SCITOOLFLOW_API_KEY"}
    if not required <= values.keys() or any(
        not k.startswith("SCITOOLFLOW_API_") or not isinstance(v, str) or not v
        for k, v in values.items()
    ):
        raise ValueError("Generation API profile is incomplete or contains unrelated settings")
    save_settings(folder / "services.env", {**values, "SCITOOLFLOW_API_PROFILE": name})


def check_api():
    """One small billed generation using the same client as SciMas."""
    from src.utils.paths import load_environment
    from src.models.client import GenerationClient

    load_environment()
    client = GenerationClient("api")
    try:
        with client.generation_scope():
            reply = client.request(
                [
                    {
                        "role": "user",
                        "content": 'Return exactly this JSON object: {"ok":true}',
                    }
                ],
                max_tokens=1024,
            )
        if json.loads(reply["text"]) != {"ok": True}:
            raise ValueError("API responded, but the JSON probe did not match")
        print(
            json.dumps(
                {
                    "ok": True,
                    "requested_model": reply.get("request_model", client.model),
                    "returned_model": reply.get("model"),
                    "duration_seconds": reply.get("duration_seconds"),
                    "usage": reply.get("usage"),
                },
                ensure_ascii=False,
            )
        )
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=Path,
        default=project_root() / "configs/services/dpsk_api.json",
    )
    parser.add_argument(
        "--use", metavar="NAME",
        help="Activate a saved local profile such as official or school; no API request",
    )
    parser.add_argument(
        "--settings-only",
        action="store_true",
        help="Save the public profile without prompting for or changing a key",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only test saved configuration with one small generation request",
    )
    args = parser.parse_args()
    try:
        if args.use:
            if args.check or args.settings_only:
                raise ValueError("Use --use separately from --check and --settings-only")
            use_profile(args.use)
            print("Active generation API profile: " + args.use)
            return
        if args.check:
            if args.settings_only:
                raise ValueError("Use --check separately from --settings-only")
            check_api()
            return
        values = json.loads(args.profile.read_text())
        if not isinstance(values, dict) or any(
            not k.startswith("SCITOOLFLOW_API_") or "KEY" in k or not isinstance(v, str)
            for k, v in values.items()
        ):
            raise ValueError(
                "Profile must contain only string generation API settings, without keys"
            )
        if not args.settings_only:
            values["SCITOOLFLOW_API_KEY"] = hidden_key()
        values.setdefault("SCITOOLFLOW_API_PROFILE", args.profile.stem)
        target = project_root() / ".local/credentials/services.env"
        save_settings(target, values)
        print("Saved generation API settings to " + str(target) + " (mode 600).")
        print(
            "API key saved."
            if not args.settings_only
            else "API key unchanged; hidden input is still required if no key was configured."
        )
    except (ValueError, OSError, RuntimeError, getpass.GetPassWarning) as error:
        # Do not echo dotenv values, provider bodies or exceptions containing user
        # input. The production client separately sanitizes HTTP diagnostics.
        safe = str(error)
        if not safe.startswith(
            (
                "Generation API",
                "API generation requires",
                "Configure --model",
                "API key must",
                "Run this command",
                "Credential file must",
                "Profile must",
                "API responded",
                "Use --check",
            )
        ):
            safe = "Check the interactive terminal, profile and local configuration."
        print("Configuration/check failed: " + safe, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
