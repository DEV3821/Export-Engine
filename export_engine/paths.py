"""Store path resolution and layout creation."""

import os
from .config import default_store_root, STORE_LAYOUT, VAULT_LAYOUT


def get_store_root(override: str | None = None) -> str:
    """Return the resolved store root path."""
    if override:
        return os.path.abspath(override)
    return os.path.abspath(default_store_root())


def ensure_store_layout(store_root: str) -> list[str]:
    """Create the required store subfolder layout.

    Returns a list of created-or-already-existed folder paths.
    """
    created: list[str] = []
    for folder in STORE_LAYOUT:
        path = os.path.join(store_root, folder)
        os.makedirs(path, exist_ok=True)
        created.append(path)
    return created


def ensure_vault_layout(store_root: str) -> list[str]:
    """Create the vault subfolder layout.

    Returns a list of created-or-already-existed folder paths.
    """
    vault_root = os.path.join(store_root, "vault")
    created: list[str] = []
    for folder in VAULT_LAYOUT:
        path = os.path.join(vault_root, folder)
        os.makedirs(path, exist_ok=True)
        created.append(path)
    return created


def resolve_user_appdata() -> str:
    """Resolve the default AppData KnowledgeStore path for the current user."""
    return get_store_root()
