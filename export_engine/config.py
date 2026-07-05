"""Default configuration for the Engine Exporter — Local Mailbox Export Engine.

Store path is currently at the legacy-compatible %LOCALAPPDATA%\\SAMI\\KnowledgeStore
location.  Path migration to %LOCALAPPDATA%\\EngineExporter\\KnowledgeStore can be
considered in a future phase with backup/restore tests.
"""

import getpass
import os

# ── Default Store Path ──────────────────────────────────────────────────

def default_store_root() -> str:
    """Return the default evidence store root path.

    Resolves to:
        C:\\Users\\<current_user>\\AppData\\Local\\SAMI\\KnowledgeStore\\
    """
    user = getpass.getuser()
    return os.path.join(
        "C:\\", "Users", user, "AppData", "Local", "SAMI", "KnowledgeStore"
    )


# ── Store Subfolder Layout ──────────────────────────────────────────────

STORE_LAYOUT = (
    "config",
    "catalog",
    "records",
    "extracts",
    "conversations",
    "retrieval",
    "state",
    "runs",
    "logs",
    "temp",
    "vault",
)

VAULT_LAYOUT = (
    "00_Dashboards",
    "05_Canvases",
    "10_Conversations",
    "20_Projects",
    "30_People",
    "40_Systems",
    "50_Tickets",
    "90_Review",
    ".sami_backups",
)

# ── Safety Flags ────────────────────────────────────────────────────────

MAILBOX_WRITE_DISABLED = True
KANBAN_WRITE_DISABLED = True
CLOUD_API_CALLS_DISABLED = True
RAW_SOURCE_RETENTION_DISABLED = True
OUTLOOK_SCOPE = "primary user store only"
NEAR_LIVE_MODE = "polling incremental refresh, not mailbox mutation"
DEFAULT_POLLING_INTERVAL = 5  # minutes
MINIMUM_POLLING_INTERVAL = 1  # minute

# ── Forbidden Path Fragments ────────────────────────────────────────────

FORBIDDEN_STORE_FRAGMENTS = (
    "OneDrive",
    "Dropbox",
    "Google Drive",
    "Desktop",
    "Downloads",
    "USB",
    "UNC",
    "Team_ESMI",
)

# ── Forbidden Root Prefixes ─────────────────────────────────────────────

FORBIDDEN_STORE_PREFIXES = (
    "\\\\",      # UNC paths
    "//",        # UNC paths (forward-slash form)
)

# ── Outlook Folder Default Exclusions ───────────────────────────────────

# Default roles that are always excluded from source scanning.
EXCLUDED_FOLDER_ROLES = frozenset({
    "deleted",
    "junk",
    "drafts",
    "outbox",
    "sync_issues",
    "rss",
    "conversation_history",
    "calendar",
    "contacts",
    "tasks",
    "notes",
    "search",
})

# Default display names that are excluded even when the role is unknown.
EXCLUDED_FOLDER_NAMES = frozenset({
    "deleted items",
    "junk email",
    "drafts",
    "outbox",
    "sync issues",
    "rss feeds",
    "conversation history",
    "calendar",
    "contacts",
    "tasks",
    "notes",
    "search folders",
})

# Store types excluded by default.
EXCLUDED_STORE_TYPES = ("shared", "archive")
