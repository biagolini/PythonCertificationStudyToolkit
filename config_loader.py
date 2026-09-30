"""Shared configuration loader for the Slack Toolkit scripts.

Workspace definitions (labels and which environment variable holds each token)
live in an external JSON file that is kept out of version control, so no
workspace-specific data is hardcoded in the scripts. The actual tokens are read
from environment variables named by the JSON, never stored in the JSON itself.
"""

import json
import sys
from pathlib import Path

# The real config lives in config/workspaces.json (git-ignored). A template
# with placeholders is versioned in config-example/workspaces.json.
CONFIG_DIR = Path(__file__).resolve().parent / "config"
WORKSPACES_FILE = CONFIG_DIR / "workspaces.json"
EXAMPLE_FILE = Path(__file__).resolve().parent / "config-example" / "workspaces.json"


def load_workspaces():
    """Return the list of workspaces from config/workspaces.json.

    Each item is a dict with at least "label" and "token_env". Exits with an
    instructive message if the file is missing or malformed.
    """
    if not WORKSPACES_FILE.exists():
        print(f"Arquivo de configuração não encontrado: {WORKSPACES_FILE}")
        print(f"Copie o exemplo e edite com seus dados:")
        print(f"  cp {EXAMPLE_FILE} {WORKSPACES_FILE}")
        sys.exit(1)

    try:
        with open(WORKSPACES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"JSON inválido em {WORKSPACES_FILE}: {e}")
        sys.exit(1)

    workspaces = data.get("workspaces")
    if not isinstance(workspaces, list) or not workspaces:
        print(f"'{WORKSPACES_FILE}' deve conter uma lista não vazia em 'workspaces'.")
        sys.exit(1)

    for i, ws in enumerate(workspaces):
        if "label" not in ws or "token_env" not in ws:
            print(f"Workspace #{i} inválido: precisa de 'label' e 'token_env'.")
            sys.exit(1)

    return workspaces


def get_default_index(workspaces):
    """Return the index of the workspace marked as default, or 0."""
    for i, ws in enumerate(workspaces):
        if ws.get("default"):
            return i
    return 0
