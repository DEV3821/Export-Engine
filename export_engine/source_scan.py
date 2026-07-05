"""Source scan orchestration — delegates to live Outlook or fixture source."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .paths import get_store_root, ensure_store_layout
from .config import OUTLOOK_SCOPE


def run_source_scan(
    store_root: str | None = None,
    *,
    use_fixture: bool = False,
    include_deleted: bool = False,
    include_junk: bool = False,
    include_drafts: bool = False,
) -> dict:
    """Run a source scan against the primary Outlook store (or fixture).

    Returns the catalog dict.
    """
    resolved_root = get_store_root(store_root)
    ensure_store_layout(resolved_root)

    if use_fixture:
        from .fixture_source import scan_fixture_source
        return scan_fixture_source(
            resolved_root,
            include_deleted=include_deleted,
            include_junk=include_junk,
            include_drafts=include_drafts,
        )
    else:
        from .outlook_com_source import scan_primary_store
        return scan_primary_store(
            resolved_root,
            include_deleted=include_deleted,
            include_junk=include_junk,
            include_drafts=include_drafts,
        )
