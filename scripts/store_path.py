"""Where the store checkout is, defined once for every script here.

STORE_REPO names it: the environment variable when set, else ../../store,
resolved against the site's repo root (an absolute STORE_REPO is used as is).
The justfile exports the same STORE_REPO, so recipes and scripts agree.

The scripts run as `python3 -I`, so they load this file through importlib:
    spec = importlib.util.spec_from_file_location("store_path", <scripts>/store_path.py)
"""
import os
from pathlib import Path

DEFAULT = "../../store"
SITE = Path(__file__).resolve().parent.parent
STORE = (SITE / (os.environ.get("STORE_REPO") or DEFAULT)).resolve()
CATALOG = STORE / "gen" / "apps.json"
CONTACT = STORE / "gen" / "contact.json"
NEEDS = f"needs the store checkout (STORE_REPO, default {DEFAULT})"


def missing():
    """The error for a store checkout that is not there, naming where it looked."""
    return f"{NEEDS}; {STORE} is not a directory"
