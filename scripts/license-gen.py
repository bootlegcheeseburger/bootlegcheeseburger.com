#!/usr/bin/env python3
"""The license sentence in each app's buy fine print, from the store catalog.

Reads <store>/gen/apps.json (owned by the store checkout, STORE_REPO: see
scripts/store_path.py) and rewrites every region of index.html between a pair
of markers
  <!-- license:gen <app> begin -->...<!-- license:gen <app> end -->
with that app's `license.long`, HTML-escaped, nothing else (no surrounding
whitespace). The text around the markers (refunds, Merchant of Record, Terms
and Privacy links) is hand-written and left alone.

Fails (exit 1, writes nothing) on a marker naming an app with no `license` in
the catalog, and on malformed markers: a `license:gen` comment that is not
exactly `<!-- license:gen <app> begin|end -->`, an unpaired or nested marker,
or an end naming another app than its begin.

Usage: python3 -I scripts/license-gen.py   (`just tool-license`)
scripts/license-check.py imports this file to regenerate and compare.
"""

import html
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
MARKER = re.compile(r"<!-- license:gen ([a-z0-9-]+) (begin|end) -->")
LOOSE = re.compile(r"<!--[^>]*?license:gen")


class GenError(Exception):
    pass


def marker(app, end):
    return f"<!-- license:gen {app} {'end' if end else 'begin'} -->"


def load_catalog():
    if not STORE.is_dir():
        raise GenError(store_path.missing())
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GenError(f"cannot read {CATALOG} ({e}); {store_path.NEEDS}")


def licenses(catalog):
    """{app: license.long} for every catalog app with a license."""
    out = {}
    for app, entry in catalog.items():
        lic = entry.get("license") if isinstance(entry, dict) else None
        if lic is None:
            continue
        long = lic.get("long") if isinstance(lic, dict) else None
        if not isinstance(long, str) or not long.strip():
            raise GenError(f"{app}'s license in the store catalog has no string `long`")
        out[app] = long
    return out


def render(long):
    """A region's text for a license.long."""
    return html.escape(long)


def regions_of(page):
    """[(app, start, end)] of every region in the page, in order: start..end is
    the text between the markers. GenError on malformed or unbalanced markers."""
    found = list(MARKER.finditer(page))
    if len(LOOSE.findall(page)) != len(found):
        raise GenError(f"{PAGE} has a `license:gen` comment that is not "
                       "`<!-- license:gen <app> begin -->` or `<!-- license:gen <app> end -->`")
    out = []
    open_ = None
    for m in found:
        app, kind = m.group(1), m.group(2)
        line = page.count("\n", 0, m.start()) + 1
        if kind == "begin":
            if open_:
                raise GenError(f"{PAGE}:{line}: `{m.group()}` opens inside the {open_[0]} region")
            open_ = (app, m.end())
        else:
            if not open_:
                raise GenError(f"{PAGE}:{line}: `{m.group()}` has no begin")
            if open_[0] != app:
                raise GenError(f"{PAGE}:{line}: `{m.group()}` closes the {open_[0]} region")
            out.append((app, open_[1], m.start()))
            open_ = None
    if open_:
        raise GenError(f"{PAGE}: `{marker(open_[0], False)}` has no end")
    return out


def build(page, catalog):
    """The page with every region rewritten from the catalog."""
    lic = licenses(catalog)
    regions = regions_of(page)
    missing = sorted({app for app, _, _ in regions if app not in lic})
    if missing:
        raise GenError(f"{PAGE} has license:gen regions for {', '.join(missing)}, "
                       "which have no license in the store catalog")
    for app, start, end in reversed(regions):
        page = page[:start] + render(lic[app]) + page[end:]
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
        print(f"license-gen: {e}", file=sys.stderr)
        return 1
    apps = sorted({app for app, _, _ in regions_of(new)})
    if new != page:
        path.write_text(new, encoding="utf-8")
        print(f"license-gen: wrote {PAGE}")
    else:
        print(f"license-gen: {PAGE} already current")
    print(f"  regions: {', '.join(apps) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
