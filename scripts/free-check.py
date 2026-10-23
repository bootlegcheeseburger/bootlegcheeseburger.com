#!/usr/bin/env python3
"""The "Free!" ribbons and the eyebrows' "Free" on index.html never drift from the store catalog.

index.html's `free:gen <app> badge|eyebrow` regions (written by
`just tool-free`, scripts/free-gen.py) are checked against
<store>/gen/apps.json with the same code. It fails when:
  1. a region's text differs from what free-gen would write (the ribbon span
     or "Free &middot; " when the app's `status` is "free", empty otherwise);
  2. a showcase (`<article id="app-<app>" class="showcase ...">`) of a catalog
     app lacks its badge region (in `.showcase-art`, right after the icon img)
     or its eyebrow region (in `.showcase-eyebrow`), or has one twice;
  3. a region names an app not in the catalog, or sits anywhere but its
     place in that app's showcase;
  4. a `free-badge` element sits outside a badge region, or a catalog app's
     eyebrow says "Free" outside its region, so a hand-placed one cannot slip in;
  5. the markers are malformed or unbalanced.
A showcase of an app not in the catalog (a draft card) needs no regions.
Reads only; never writes. Every problem is reported in one run; exit 1 on any.

Usage: python3 -I scripts/free-check.py [--rev REV]
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
FIX = "run `just tool-free` and commit"
ARTICLE = re.compile(r"<article\b([^>]*)>(.*?)</article>", re.S)
APP_ID = re.compile(r'\bid="app-([a-z0-9-]+)"')
SHOWCASE = re.compile(r'\bclass="[^"]*(?<![\w-])showcase(?![\w-])')
ART = re.compile(r'<div\b[^>]*\bclass="[^"]*(?<![\w-])showcase-art(?![\w-])[^"]*"[^>]*>')
ICON = re.compile(r"\s*<img\b[^>]*>\s*")
EYEBROW = re.compile(r'<div\b[^>]*\bclass="[^"]*(?<![\w-])showcase-eyebrow(?![\w-])[^"]*"[^>]*>(.*?)</div>', re.S)
BADGE = re.compile(r'\bclass="[^"]*(?<![\w-])free-badge(?![\w-])')
FREE_WORD = re.compile(r"\bFree\b")


def load_gen():
    spec = importlib.util.spec_from_file_location("free_gen", os.path.join(SITE, "scripts", "free-gen.py"))
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


def showcases(page):
    """{app: (badge_at, eyebrow)} per showcase: badge_at is where the badge
    region's begin marker belongs (right after the icon img in .showcase-art,
    or None), eyebrow the (start, end) of the eyebrow's text (or None)."""
    out = {}
    for a in ARTICLE.finditer(page):
        app = APP_ID.search(a.group(1))
        if not app or not SHOWCASE.search(a.group(1)):
            continue
        badge_at = eyebrow = None
        art = ART.search(page, a.start(2), a.end(2))
        if art:
            icon = ICON.match(page, art.end())
            if icon:
                badge_at = icon.end()
        eb = EYEBROW.search(page, a.start(2), a.end(2))
        if eb:
            eyebrow = (eb.start(1), eb.end(1))
        out[app.group(1)] = (badge_at, eyebrow)
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
        free = gen.free_apps(gen.load_catalog())
    except gen.GenError as e:
        print(f"free-check: {e}", file=sys.stderr)
        return 1

    page = read_index(rev)
    if page is None:
        print(f"free-check: index.html is missing{where}", file=sys.stderr)
        return 1
    try:
        regions = gen.regions_of(page)
    except gen.GenError as e:
        print(f"free-check: {e}{where}: fix the markers, then {FIX}", file=sys.stderr)
        return 1

    def line(pos):
        return page.count("\n", 0, pos) + 1

    cards = showcases(page)
    problems = []
    seen = {}
    for app, part, start, end in regions:
        seen.setdefault((app, part), []).append(start)
        if app not in free:
            problems.append(f"index.html:{line(start)}{where}: a free:gen {part} region names {app}, which is not "
                            "in the store catalog: remove the region")
            continue
        begin = start - len(gen.marker(app, part, False))
        end_marker = end + len(gen.marker(app, part, True))
        badge_at, eyebrow = cards.get(app, (None, None))
        if part == "badge" and begin != badge_at:
            problems.append(f"index.html:{line(start)}{where}: the {app} badge region is not right after the icon "
                            f"img in #app-{app} .showcase-art: move it there")
        elif part == "eyebrow" and not (eyebrow and eyebrow[0] <= begin and end_marker <= eyebrow[1]):
            problems.append(f"index.html:{line(start)}{where}: the {app} eyebrow region is not inside "
                            f"#app-{app} .showcase-eyebrow: move it there")
        want = gen.render(part, free[app])
        if page[start:end] != want:
            problems.append(f"index.html:{line(start)}{where}: the {app} {part} region is stale against "
                            f"the store catalog (status {'free' if free[app] else 'not free'}): {FIX}\n"
                            f"  site:  {page[start:end][:200]!r}\n"
                            f"  store: {want!r}")
    for (app, part), starts in seen.items():
        if len(starts) > 1:
            problems.append(f"index.html:{line(starts[1])}{where}: {app} has {len(starts)} free:gen {part} regions; "
                            "keep one")
    for app, (badge_at, eyebrow) in sorted(cards.items()):
        if app not in free:
            continue
        for part in gen.PARTS:
            if (app, part) not in seen:
                place = (".showcase-art, right after the icon img" if part == "badge"
                         else ".showcase-eyebrow, where \"Free &middot; \" goes")
                problems.append(f"index.html{where}: {app} is in the store catalog but its showcase "
                                f"(#app-{app}) has no free:gen {part} region: put "
                                f"`{gen.marker(app, part, False)}{gen.marker(app, part, True)}` in its {place}, "
                                f"then {FIX}")
        if eyebrow:
            # the eyebrow's text with its regions' contents cut out
            text, pos = "", eyebrow[0]
            for _, part, start, end in regions:
                if part == "eyebrow" and eyebrow[0] <= start and end <= eyebrow[1]:
                    text, pos = text + page[pos:start], end
            text += page[pos:eyebrow[1]]
            if FREE_WORD.search(text):
                problems.append(f"index.html:{line(eyebrow[0])}{where}: {app}'s eyebrow says \"Free\" outside its "
                                f"free:gen eyebrow region: remove it (the region writes it), then {FIX}")
    for m in BADGE.finditer(page):
        if not any(part == "badge" and start <= m.start() < end for _, part, start, end in regions):
            problems.append(f"index.html:{line(m.start())}{where}: a free-badge sits outside a free:gen badge "
                            f"region: remove it (the region writes it), then {FIX}")

    for p in problems:
        print(f"free-check: {p}", file=sys.stderr)
    if problems:
        return 1
    apps = sorted({a for a, _, _, _ in regions if free.get(a)})
    print(f"free-check: ok{where} ({', '.join(apps) or 'no free apps on the site'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
