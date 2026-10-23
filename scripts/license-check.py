#!/usr/bin/env python3
"""The license sentence in the buy fine print never drifts from the store catalog.

index.html's `license:gen <app>` regions (written by `just tool-license`,
scripts/license-gen.py) are checked against <store>/gen/apps.json with the
same code. It fails when:
  1. a region's text differs from what license-gen would write (the app's
     `license.long`, HTML-escaped);
  2. a region names an app with no `license` in the catalog;
  3. an app with a license has a buy fine print on its showcase (a
     `<p class="buy-fine">` inside `<article id="app-<app>">`) holding no
     region for it;
  4. the markers are malformed or unbalanced.
A licensed app with no buy fine print on the site (no showcase, or a showcase
with no Buy box yet) is not an error. Reads only; never writes. Every problem
is reported in one run; exit 1 on any.

Usage: python3 -I scripts/license-check.py [--rev REV]
  --rev REV  check index.html as committed at REV (the pre-push hook passes
             each pushed commit) instead of the working tree.
Run by `just dev-check` and .githooks/pre-push. <store> is the store checkout
(STORE_REPO, see scripts/store_path.py).
"""
import importlib.util
import os
import re
import subprocess
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = "run `just tool-license` and commit"
ARTICLE = re.compile(r"<article\b([^>]*)>(.*?)</article>", re.S)
APP_ID = re.compile(r'\bid="app-([a-z0-9-]+)"')
FINE = re.compile(r'<p\b[^>]*\bclass="[^"]*(?<![\w-])buy-fine(?![\w-])[^"]*"[^>]*>(.*?)</p>', re.S)


def load_gen():
    spec = importlib.util.spec_from_file_location("license_gen", os.path.join(SITE, "scripts", "license-gen.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_index(rev):
    if rev is None:
        try:
            with open(os.path.join(SITE, "index.html"), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None
    r = subprocess.run(["git", "-C", SITE, "cat-file", "blob", f"{rev}:index.html"], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def fine_prints(page):
    """[(app, start, end)] of each buy fine print's text inside an app's article."""
    out = []
    for a in ARTICLE.finditer(page):
        app = APP_ID.search(a.group(1))
        if not app:
            continue
        for p in FINE.finditer(page, a.start(2), a.end(2)):
            out.append((app.group(1), p.start(1), p.end(1)))
    return out


def main(argv):
    rev = None
    if argv[:1] == ["--rev"] and len(argv) == 2:
        rev = argv[1]
    elif argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2

    gen = load_gen()
    where = f" at {rev[:12]}" if rev else ""
    try:
        lic = gen.licenses(gen.load_catalog())
    except gen.GenError as e:
        print(f"license-check: {e}", file=sys.stderr)
        return 1

    page = read_index(rev)
    if page is None:
        print(f"license-check: index.html is missing{where}", file=sys.stderr)
        return 1
    try:
        regions = gen.regions_of(page)
    except gen.GenError as e:
        print(f"license-check: {e}{where}: fix the markers, then {FIX}", file=sys.stderr)
        return 1

    def line(pos):
        return page.count("\n", 0, pos) + 1

    problems = []
    for app, start, end in regions:
        if app not in lic:
            problems.append(f"index.html:{line(start)}{where}: a license:gen region names {app}, which has no "
                            "license in the store catalog: remove the region")
        elif page[start:end] != gen.render(lic[app]):
            problems.append(f"index.html:{line(start)}{where}: the {app} license text is stale against "
                            f"the store catalog: {FIX}\n"
                            f"  site:  {page[start:end][:200]!r}\n"
                            f"  store: {gen.render(lic[app])[:200]!r}")
    for app, start, end in fine_prints(page):
        if app in lic and not any(a == app and start <= s and e <= end for a, s, e in regions):
            problems.append(f"index.html:{line(start)}{where}: {app} has a license in the store catalog "
                            f"but its buy fine print (#app-{app} .buy-fine) has no license:gen region: put "
                            f"`{gen.marker(app, False)}{gen.marker(app, True)}` where the license sentence "
                            f"goes, then {FIX}")

    for p in problems:
        print(f"license-check: {p}", file=sys.stderr)
    if problems:
        return 1
    apps = sorted({a for a, _, _ in regions})
    print(f"license-check: ok{where} ({', '.join(apps) or 'no license regions'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
