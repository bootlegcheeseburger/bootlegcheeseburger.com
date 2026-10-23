#!/usr/bin/env python3
"""The "Free!" ribbon and the eyebrow's "Free" on each app card, from the store catalog.

Reads <store>/gen/apps.json (owned by the store checkout, STORE_REPO: see
scripts/store_path.py) and rewrites every region of index.html between a pair
of markers
  <!-- free:gen <app> badge begin -->...<!-- free:gen <app> badge end -->
  <!-- free:gen <app> eyebrow begin -->...<!-- free:gen <app> eyebrow end -->
When the app's catalog `status` is "free", the badge region holds
`<span class="free-badge" aria-hidden="true">Free!</span>` and the eyebrow
region holds `Free &middot; `; otherwise both are empty. Nothing else, no
surrounding whitespace. The badge region sits in the showcase's
`.showcase-art`, right after the icon img; the eyebrow region sits in its
`.showcase-eyebrow` where "Free &middot; " goes. Placement is hand-written;
scripts/free-check.py checks it.

Fails (exit 1, writes nothing) on a region naming an app not in the catalog,
and on malformed markers: a `free:gen` comment that is not exactly
`<!-- free:gen <app> badge|eyebrow begin|end -->`, an unpaired or nested
marker, or an end naming another app or part than its begin.

Usage: python3 -I scripts/free-gen.py   (`just tool-free`)
scripts/free-check.py imports this file to regenerate and compare.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("store_path", ROOT / "scripts" / "store_path.py")
store_path = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store_path)
STORE = store_path.STORE
CATALOG = store_path.CATALOG
PAGE = "index.html"
PARTS = ("badge", "eyebrow")
MARKER = re.compile(r"<!-- free:gen ([a-z0-9-]+) (badge|eyebrow) (begin|end) -->")
LOOSE = re.compile(r"<!--[^>]*?free:gen")
BADGE = '<span class="free-badge" aria-hidden="true">Free!</span>'
EYEBROW = "Free &middot; "


class GenError(Exception):
    pass


def marker(app, part, end):
    return f"<!-- free:gen {app} {part} {'end' if end else 'begin'} -->"


def load_catalog():
    if not STORE.is_dir():
        raise GenError(store_path.missing())
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GenError(f"cannot read {CATALOG} ({e}); {store_path.NEEDS}")


def free_apps(catalog):
    """{app: is free} for every catalog app."""
    return {app: isinstance(e, dict) and e.get("status") == "free" for app, e in catalog.items()}


def render(part, free):
    """A region's text."""
    if not free:
        return ""
    return BADGE if part == "badge" else EYEBROW


def regions_of(page):
    """[(app, part, start, end)] of every region in the page, in order:
    start..end is the text between the markers. GenError on malformed or
    unbalanced markers."""
    found = list(MARKER.finditer(page))
    if len(LOOSE.findall(page)) != len(found):
        raise GenError(f"{PAGE} has a `free:gen` comment that is not "
                       "`<!-- free:gen <app> badge|eyebrow begin|end -->`")
    out = []
    open_ = None
    for m in found:
        app, part, kind = m.group(1), m.group(2), m.group(3)
        line = page.count("\n", 0, m.start()) + 1
        if kind == "begin":
            if open_:
                raise GenError(f"{PAGE}:{line}: `{m.group()}` opens inside the {open_[0]} {open_[1]} region")
            open_ = (app, part, m.end())
        else:
            if not open_:
                raise GenError(f"{PAGE}:{line}: `{m.group()}` has no begin")
            if open_[:2] != (app, part):
                raise GenError(f"{PAGE}:{line}: `{m.group()}` closes the {open_[0]} {open_[1]} region")
            out.append((app, part, open_[2], m.start()))
            open_ = None
    if open_:
        raise GenError(f"{PAGE}: `{marker(open_[0], open_[1], False)}` has no end")
    return out


def build(page, catalog):
    """The page with every region rewritten from the catalog."""
    free = free_apps(catalog)
    regions = regions_of(page)
    missing = sorted({app for app, _, _, _ in regions if app not in free})
    if missing:
        raise GenError(f"{PAGE} has free:gen regions for {', '.join(missing)}, "
                       "which are not in the store catalog")
    for app, part, start, end in reversed(regions):
        page = page[:start] + render(part, free[app]) + page[end:]
    return page


def main(argv):
    if argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    path = ROOT / PAGE
    try:
        catalog = load_catalog()
        page = path.read_text(encoding="utf-8")
        new = build(page, catalog)
    except GenError as e:
        print(f"free-gen: {e}", file=sys.stderr)
        return 1
    free = free_apps(catalog)
    apps = sorted({app for app, _, _, _ in regions_of(new)})
    if new != page:
        path.write_text(new, encoding="utf-8")
        print(f"free-gen: wrote {PAGE}")
    else:
        print(f"free-gen: {PAGE} already current")
    print(f"  free: {', '.join(a for a in apps if free[a]) or 'none'}")
    print(f"  not free: {', '.join(a for a in apps if not free[a]) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
