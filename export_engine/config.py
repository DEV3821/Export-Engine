"""Default configuration for the Local Knowledge Store Export Engine."""

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
