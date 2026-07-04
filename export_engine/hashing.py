"""Stable hashing helpers for deterministic key generation.

All evidence filenames MUST be hash-based.  Email subjects, attachment names,
or any user-derived text MUST NOT be used as filenames directly.
"""

import hashlib
import json
import re
import string


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def stable_json_hash(obj: object) -> str:
    """Return a deterministic SHA-256 hash of a JSON-serialisable object.

    Keys are sorted so identical dicts produce identical hashes.
    """
    serialised = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return sha256_text(serialised)


def short_hash(text: str, length: int = 12) -> str:
    """Return the first *length* characters of the SHA-256 hex digest."""
    return sha256_text(text)[:length]


def make_record_key(folder_path: str, subject: str, sent_at: str) -> str:
    """Deterministic record key from folder, subject, and timestamp."""
    raw = f"{folder_path}|{subject}|{sent_at}"
    return stable_json_hash({"folder": folder_path, "subject": subject, "sent_at": sent_at})


def make_extract_key(record_key: str, extract_type: str) -> str:
    """Deterministic extract sidecar key."""
    raw = f"{record_key}|{extract_type}"
    return sha256_text(raw)


def make_conversation_key(conversation_id: str) -> str:
    """Deterministic conversation key."""
    return sha256_text(conversation_id)


def make_chunk_id(record_key: str, chunk_index: int) -> str:
    """Deterministic retrieval chunk identifier."""
    raw = f"{record_key}|chunk:{chunk_index}"
    return sha256_text(raw)


def make_folder_key(folder_path: str) -> str:
    """Deterministic folder / source-catalog key."""
    return sha256_text(folder_path)


def make_store_id_hash(store_id: str) -> str:
    """Deterministic hash of a store identifier."""
    return sha256_text(store_id)


def safe_filename(digest: str, suffix: str = ".json") -> str:
    """Build a filesystem-safe filename from a hex digest.

    The digest itself is always safe (hex chars).  This function
    ensures the result is safe even if called with unsafe input.
    """
    safe = re.sub(r"[^a-fA-F0-9]", "", digest)[:64]
    if not safe:
        safe = "a" * 8  # fallback for edge case
    return f"{safe}{suffix}"


# Characters safe for filenames across Windows, macOS, and Linux.
_FS_SAFE = frozenset(string.ascii_letters + string.digits + "-_.")
