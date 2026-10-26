"""Where the store checkout is, defined once for every script here.

STORE_REPO names it, from the environment only: the shared shop recipes the
justfile imports export it, so run the scripts through just (or set it). A
relative STORE_REPO resolves against the site's repo root.

The scripts run as `python3 -I`, so they load this file through importlib:
    spec = importlib.util.spec_from_file_location("store_path", <scripts>/store_path.py)
"""
import os
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
if not os.environ.get("STORE_REPO"):
    sys.exit("STORE_REPO unset: run through just (core.just exports it; `just tool-link` if .blc is missing)")
STORE = (SITE / os.environ["STORE_REPO"]).resolve()
CATALOG = STORE / "gen" / "apps.json"
CONTACT = STORE / "gen" / "contact.json"
NEEDS = "needs the store checkout (STORE_REPO)"


def missing():
    """The error for a store checkout that is not there, naming where it looked."""
    return f"{NEEDS}; {STORE} is not a directory"
