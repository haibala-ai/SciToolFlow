"""Chroma's authorized weight download, with bounded requests and private credentials."""

from scitoolflow.paths import local_root, artifacts_root
import hashlib
import json
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor
import os
import time
from tools.runtime.config import Config

ROOT = local_root()


def _range_download(base_url, weights_name, temporary):
    parameters = {"token": Config().CHROMA_KEY, "weights": weights_name}

    def session():
        client = requests.Session()
        client.trust_env = os.getenv("SCITOOL_CHROMA_USE_PROXY", "1") == "1"
        return client

    with session() as client, client.get(
        base_url,
        params=parameters,
        headers={"Range": "bytes=0-0"},
        stream=True,
        timeout=(15, 30),
    ) as response:
        if response.status_code != 206 or not response.headers.get("Content-Range"):
            raise RuntimeError(
                "Chroma weight server did not support the verified range route"
            )
        total = int(response.headers["Content-Range"].split("/")[-1])
    chunk_size = 2 * 1024 * 1024
    parts = temporary.with_name(temporary.name + ".parts")
    parts.mkdir(exist_ok=True)
    bounds = [
        (start, min(start + chunk_size, total)) for start in range(0, total, chunk_size)
    ]
    # Preserve complete blocks from an interrupted sequential transfer.
    if temporary.exists():
        with temporary.open("rb") as old:
            for start, end in bounds:
                if end > temporary.stat().st_size:
                    break
                target = parts / f"{start}-{end}"
                if not target.exists():
                    target.write_bytes(old.read(end - start))
                else:
                    old.seek(end)

    def fetch(bound):
        start, end = bound
        target = parts / f"{start}-{end}"
        if target.exists() and target.stat().st_size == end - start:
            return target
        for attempt in range(6):
            try:
                with session() as client, client.get(
                    base_url,
                    params=parameters,
                    headers={
                        "Range": f"bytes={start}-{end - 1}",
                        "Accept-Encoding": "identity",
                    },
                    stream=True,
                    timeout=(15, 30),
                ) as response:
                    if (
                        response.status_code != 206
                        or response.headers.get("Content-Range")
                        != f"bytes {start}-{end - 1}/{total}"
                    ):
                        raise RuntimeError("Unexpected Chroma HTTP range response")
                    with target.open("wb") as file:
                        for block in response.iter_content(256 * 1024):
                            file.write(block)
                if target.stat().st_size != end - start:
                    raise RuntimeError("Incomplete Chroma HTTP range")
                return target
            except (requests.RequestException, RuntimeError):
                if attempt == 5:
                    raise RuntimeError(
                        f"Chroma range download failed for block {start}"
                    ) from None
                time.sleep(2)

    with ThreadPoolExecutor(max_workers=4) as pool:
        completed = list(pool.map(fetch, bounds))
    digest = hashlib.sha256()
    with temporary.open("wb") as file:
        for target in completed:
            with target.open("rb") as source:
                while block := source.read(1024 * 1024):
                    file.write(block)
                    digest.update(block)
    if temporary.stat().st_size != total:
        raise RuntimeError("Incomplete assembled Chroma file")
    return digest.hexdigest()


def download_from_generate(
    base_url, weights_name, force=False, exist_ok=False, key_directory=None
):
    if Path(weights_name).name != weights_name or not weights_name.endswith(".pt"):
        raise ValueError("Expected a Chroma .pt weight filename")
    directory = ROOT / "models/chroma"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / weights_name
    record_file = directory / (weights_name + ".json")
    if target.exists() and record_file.exists() and exist_ok and not force:
        record = json.loads(record_file.read_text())
        if target.stat().st_size == record["bytes"]:
            digest = hashlib.sha256()
            with target.open("rb") as file:
                while block := file.read(4 * 1024 * 1024):
                    digest.update(block)
            if digest.hexdigest() == record["download_sha256"]:
                return str(target)
    temporary = target.with_suffix(".pt.partial")
    try:
        digest = _range_download(base_url, weights_name, temporary)
    except requests.RequestException as error:
        # requests exception strings can contain the token in the URL.
        raise RuntimeError(
            "Chroma weight download failed: " + type(error).__name__
        ) from None
    temporary.replace(target)
    record_file.write_text(
        json.dumps(
            {
                "weight": weights_name,
                "bytes": target.stat().st_size,
                "download_sha256": digest,
                "source_endpoint": base_url,
                "publisher_checksum_available": False,
            },
            indent=2,
        )
        + "\n"
    )
    return str(target)
