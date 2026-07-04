"""Path and safety guards for rejecting unsafe store locations."""

import os
import re

from .config import FORBIDDEN_STORE_FRAGMENTS, FORBIDDEN_STORE_PREFIXES


# ── Check functions ────────────────────────────────────────────────────


def _normalise_path(path: str) -> str:
    """Normalise a path to lowercase with forward slashes for matching."""
    return os.path.abspath(path).lower().replace("\\", "/")


def is_under_path(child: str, parent: str) -> bool:
    """Return True if *child* is under (or equal to) *parent*."""
    c = _normalise_path(child)
    p = _normalise_path(parent)
    return c == p or c.startswith(p + "/")


def contains_forbidden_fragment(path: str) -> bool:
    """Return True if the path contains any forbidden fragment."""
    norm = _normalise_path(path)
    for frag in FORBIDDEN_STORE_FRAGMENTS:
        if frag.lower() in norm:
            return True
    return False


def has_forbidden_prefix(path: str) -> bool:
    """Return True if the path starts with a forbidden prefix."""
    norm = _normalise_path(path)
    for prefix in FORBIDDEN_STORE_PREFIXES:
        pfx = prefix.lower().replace("\\", "/")
        if norm.startswith(pfx):
            return True
    return False


def is_removable_drive(path: str) -> bool:
    """Heuristic check if the path looks like a removable/USB drive.

    On Windows removable drives typically appear as D:\, E:\, etc.
    We check if the root is a drive letter other than C:.
    """
    norm = _normalise_path(path)
    match = re.match(r"^([a-z]):/", norm)
    if match and match.group(1) != "c":
        return True
    return False


def is_network_drive(path: str) -> bool:
    """Heuristic check if the path is a mapped network drive.

    Common mapped drive letters: Z:, Y:, X:, etc.
    We flag non-C drive letters as potentially mapped.
    """
    norm = _normalise_path(path)
    match = re.match(r"^([a-z]):/", norm)
    if match and match.group(1) not in ("c", "d", "e"):
        return True
    return False


def is_path_allowed(store_path: str, *, repo_path: str | None = None) -> bool:
    """Return True if the store path passes all safety checks."""
    # 1. Forbidden prefixes
    if has_forbidden_prefix(store_path):
        return False

    # 2. Forbidden fragments
    if contains_forbidden_fragment(store_path):
        return False

    # 3. Removable / non-C drives
    if is_removable_drive(store_path):
        return False

    # 4. Repo path guard
    if repo_path and is_under_path(store_path, repo_path):
        return False

    return True


def verify_text_absent(text: str, phrases: list[str]) -> dict[str, bool]:
    """Check that none of the banned phrases appear in *text*.

    Returns a dict mapping each phrase to whether it was found.
    """
    text_lower = text.lower()
    results: dict[str, bool] = {}
    for phrase in phrases:
        results[phrase] = phrase.lower() in text_lower
    return results
