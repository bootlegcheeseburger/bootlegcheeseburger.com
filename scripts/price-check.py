#!/usr/bin/env python3
"""App price labels and Paddle price ids on the site never drift from the store catalog.

index.html's `price:gen <app>` regions and STORE-block lines tagged
`// price:<app>` (written by `just tool-price`, scripts/price-gen.py) are
checked against <store>/gen/apps.json with the same code. It fails when:
  1. a region's label, or a tagged PRICE_LABEL / PRICE_ID, differs from what
     price-gen would write (the app's price label; its paddle live or sandbox
     price id for the block's ENV);
  2. a region or tag names an app with no `price` in the catalog (or, for a
     PRICE_ID, no paddle price id for the block's ENV), or the price is in an
     unsupported currency, or the block's ENV is not "production" or "sandbox";
  3. a PRICE_ID or PRICE_LABEL line has no `// price:<app>` tag, so a
     hand-written value cannot slip in;
  4. the markers or tags are malformed or unbalanced.
Reads only; never writes. Every problem is reported in one run; exit 1 on any.

Usage: python3 -I scripts/price-check.py [--rev REV]
  --rev REV  check index.html as committed at REV (the pre-push hook passes
             each pushed commit) instead of the working tree.
Run by `just dev-check` and .githooks/pre-push. <store> is the store checkout
(STORE_REPO, see scripts/store_path.py).
"""
import html
import importlib.util
import os
import subprocess
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = "run `just tool-price` and commit"


def load_gen():
    spec = importlib.util.spec_from_file_location("price_gen", os.path.join(SITE, "scripts", "price-gen.py"))
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
        catalog = gen.load_catalog()
    except gen.GenError as e:
        print(f"price-check: {e}", file=sys.stderr)
        return 1

    page = read_index(rev)
    if page is None:
        print(f"price-check: index.html is missing{where}", file=sys.stderr)
        return 1
    try:
        regions = gen.regions_of(page)
        tags, untagged = gen.tags_of(page)
    except gen.GenError as e:
        print(f"price-check: {e}{where}: fix the markers or tags, then {FIX}", file=sys.stderr)
        return 1

    def line(pos):
        return page.count("\n", 0, pos) + 1

    problems = []
    for app, start, end in regions:
        try:
            want = html.escape(gen.label(catalog, app))
        except gen.GenError as e:
            problems.append(f"index.html:{line(start)}{where}: a price:gen region names {app}: {e}: "
                            "remove the region or fix the store")
            continue
        if page[start:end] != want:
            problems.append(f"index.html:{line(start)}{where}: the {app} price label is stale against "
                            f"the store catalog: {FIX}\n"
                            f"  site:  {page[start:end][:200]!r}\n"
                            f"  store: {want!r}")
    for app, key, env, start, end in tags:
        try:
            want = gen.want_tag(catalog, app, key, env)
        except gen.GenError as e:
            fix = (f"set ENV, then {FIX}" if key == "PRICE_ID" and env not in gen.ENVS
                   else "remove the tag or fix the store")
            problems.append(f"index.html:{line(start)}{where}: {key} is tagged price:{app}: {e}: {fix}")
            continue
        if page[start:end] != want:
            what = f"{key} (ENV {env!r})" if key == "PRICE_ID" else key
            problems.append(f"index.html:{line(start)}{where}: the {app} {what} is stale against "
                            f"the store catalog: {FIX}\n"
                            f"  site:  {page[start:end][:200]!r}\n"
                            f"  store: {want!r}")
    for n, key in untagged:
        problems.append(gen.untagged_message(n, key, where))

    for p in problems:
        print(f"price-check: {p}", file=sys.stderr)
    if problems:
        return 1
    apps = sorted({a for a, _, _ in regions} | {t[0] for t in tags})
    print(f"price-check: ok{where} ({', '.join(apps) or 'no price regions or tags'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
