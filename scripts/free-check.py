#!/usr/bin/env python3
"""The "Free!" stickers on index.html never disagree with the store catalog.

An app's showcase (`<article id="app-<app>" class="showcase ...">` in
index.html) carries the sticker (an element with class "free-badge") exactly
when its entry in ~/Code/store/gen/apps.json has status "free". Each app with a
free status but no sticker, and each sticker on an app that is not free (or not
in the catalog), is reported; exit 1 on any. Only apps with a showcase are in
scope: a free app with no card on the site at all is not an error. Reads only;
never writes.

Usage: python3 -I scripts/free-check.py [--rev REV]
  --rev REV  check index.html as committed at REV (the pre-push hook passes
             each pushed commit) instead of the working tree.
Run by `just dev-check` and .githooks/pre-push. The store is found through HOME.
"""
import json
import os
import re
import subprocess
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.expanduser("~/Code/store")
ARTICLE = re.compile(r"<article\b([^>]*)>(.*?)</article>", re.S)
APP_ID = re.compile(r'\bid="app-([a-z0-9-]+)"')
BADGE = re.compile(r'\bclass="[^"]*(?<![\w-])free-badge(?![\w-])[^"]*"')


def read_index(rev):
    if rev is None:
        try:
            with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None
    r = subprocess.run(["git", "-C", SITE, "cat-file", "blob", f"{rev}:index.html"], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def main(argv):
    rev = None
    if argv[:1] == ["--rev"] and len(argv) == 2:
        rev = argv[1]
    elif argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2

    try:
        with open(os.path.join(STORE, "gen", "apps.json"), encoding="utf-8") as f:
            apps = json.load(f)
    except (OSError, ValueError) as e:
        print(f"free-check: cannot read ~/Code/store/gen/apps.json ({e}); needs ~/Code/store beside web", file=sys.stderr)
        return 1

    where = f" at {rev[:12]}" if rev else ""
    html = read_index(rev)
    if html is None:
        print(f"free-check: index.html is missing{where}", file=sys.stderr)
        return 1

    # app -> whether its showcase carries the sticker
    cards = {}
    for m in ARTICLE.finditer(html):
        attrs, body = m.group(1), m.group(2)
        app = APP_ID.search(attrs)
        if app and re.search(r'\bclass="[^"]*\bshowcase\b', attrs):
            cards[app.group(1)] = bool(BADGE.search(body))

    def status(app):
        e = apps.get(app)
        return e.get("status") if isinstance(e, dict) else None

    problems = []
    for app, badged in sorted(cards.items()):
        free = status(app) == "free"
        if free and not badged:
            problems.append(f"{app} is free in ~/Code/store/gen/apps.json but its showcase (#app-{app}) has no "
                            f'free-badge{where}: add `<span class="free-badge" aria-hidden="true">Free!</span>` '
                            "after its icon in .showcase-art")
        elif badged and not free:
            st = status(app)
            why = f'status "{st}"' if st else "no catalog entry"
            problems.append(f"{app} has a free-badge on its showcase (#app-{app}){where} but is not free in "
                            f"~/Code/store/gen/apps.json ({why}): remove the sticker")

    for p in problems:
        print(f"free-check: {p}", file=sys.stderr)
    if problems:
        return 1
    free = sorted(a for a, b in cards.items() if b)
    print(f"free-check: ok{where} ({', '.join(free) or 'no free apps on the site'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
