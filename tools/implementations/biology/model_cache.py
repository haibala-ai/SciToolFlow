"""Bounded process-local *resource* reuse; never cache scientific predictions."""
from pathlib import Path
from threading import RLock
from weakref import WeakKeyDictionary

_guard = RLock()
_resources = {}
_inference_locks = WeakKeyDictionary()


def checkpoint_version(checkpoint):
    """Invalidate on path, inode, byte size or modification/change timestamps.

    Configuration, vocabulary and weight files are included. No multi-GB
    content rehash is performed per inference. Missing resources are left for
    the real loader to reject. No cross-process/disk or sequence-output cache.
    """
    path = Path(checkpoint).expanduser().resolve()
    files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix in
                   {".json", ".txt", ".model", ".safetensors", ".bin", ".pt"}) if path.is_dir() else [path]
    versions = []
    for file in files:
        try:
            stat = file.stat()
            versions.append((str(file), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        except FileNotFoundError:
            versions.append((str(file), "missing"))
    return str(path), tuple(versions)


def cached_resource(namespace, checkpoint, loader, variant=()):
    """Keep at most one version/checkpoint per model-family namespace.

    Loaders must preserve model settings; only successfully loaded resources
    enter cache. Changing checkpoint files or loader variant evicts old entry.
    """
    key = checkpoint_version(checkpoint), tuple(variant)
    with _guard:
        current = _resources.get(namespace)
        if current is None or current[0] != key:
            _resources.pop(namespace, None)
            resource = loader()
            _resources[namespace] = (key, resource)
        return _resources[namespace][1]


def inference_lock(model):
    """Serialize access to a reused model's mutable generation state."""
    with _guard:
        lock = _inference_locks.get(model)
        if lock is None:
            lock = RLock()
            _inference_locks[model] = lock
        return lock
