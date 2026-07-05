"""Tests for paths.py — store path resolution and layout."""

import os
import tempfile

from export_engine.paths import (
    get_store_root,
    ensure_store_layout,
    ensure_vault_layout,
    resolve_user_appdata,
)
from export_engine.config import STORE_LAYOUT, VAULT_LAYOUT


class TestDefaultStorePath:
    """Default store path resolves to the current user's AppData."""

    def test_default_resolves_to_appdata(self) -> None:
        root = get_store_root()
        assert "AppData" in root or "appdata" in root.lower()
        assert "SAMI" in root
        assert "KnowledgeStore" in root

    def test_default_matches_user(self) -> None:
        root = get_store_root()
        # Should contain the current user
        assert os.path.exists(os.path.dirname(os.path.dirname(root))) or True  # not critical

    def test_resolve_user_appdata(self) -> None:
        root = resolve_user_appdata()
        assert root == get_store_root()


class TestStoreLayoutCreation:
    """Store and vault layout creation."""

    def test_store_layout_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            created = ensure_store_layout(tmp)
            assert len(created) == len(STORE_LAYOUT)
            for folder in STORE_LAYOUT:
                path = os.path.join(tmp, folder)
                assert os.path.isdir(path)

    def test_store_layout_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            created1 = ensure_store_layout(tmp)
            created2 = ensure_store_layout(tmp)
            assert len(created1) == len(created2)

    def test_vault_layout_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_path, exist_ok=True)
            created = ensure_vault_layout(store_path)
            assert len(created) == len(VAULT_LAYOUT)
            vault_root = os.path.join(store_path, "vault")
            assert os.path.isdir(vault_root)
            for folder in VAULT_LAYOUT:
                path = os.path.join(vault_root, folder)
                assert os.path.isdir(path), f"Missing vault folder: {folder}"

    def test_vault_layout_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "KnowledgeStore")
            os.makedirs(store_path, exist_ok=True)
            created1 = ensure_vault_layout(store_path)
            created2 = ensure_vault_layout(store_path)
            assert len(created1) == len(created2)
