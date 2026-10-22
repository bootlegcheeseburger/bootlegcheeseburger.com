#!/usr/bin/env python3
"""The contact page's mailtos never drift from the store's contact templates.

Regenerates contact.html's `contact:gen` regions (the no-JS fallback list and
the JSON data) from ~/Code/store/gen/contact.json, ~/Code/store/gen/apps.json
and the site's own index.html (which apps are public), with the same code as
`just contact` (scripts/contact-gen.py), and fails when the committed page
differs. Reads only; never writes. Exit 1 on any problem.

Usage: python3 -I scripts/contact-check.py [--rev REV]
  --rev REV  check contact.html and index.html as committed at REV (the
             pre-push hook passes each pushed commit) instead of the working tree.
Run by `just dev-check` and .githooks/pre-push. The store is found through HOME.
"""
import difflib
import importlib.util
import os
import subprocess
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = "run `just contact` and commit"


def load_gen():
    spec = importlib.util.spec_from_file_location("contact_gen", os.path.join(SITE, "scripts", "contact-gen.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def site_reader(rev):
    if rev is None:
        def read(path):
            try:
                with open(os.path.join(SITE, path), encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                return None
        return read

    def read(path):
        r = subprocess.run(["git", "-C", SITE, "cat-file", "blob", f"{rev}:{path}"], capture_output=True)
        return r.stdout.decode("utf-8") if r.returncode == 0 else None
    return read


def main(argv):
    rev = None
    if argv[:1] == ["--rev"] and len(argv) == 2:
        rev = argv[1]
    elif argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2

    gen = load_gen()
    read = site_reader(rev)
    where = f" at {rev[:12]}" if rev else ""
    try:
        contact, catalog = gen.load_store()
    except gen.GenError as e:
        print(f"contact-check: {e}", file=sys.stderr)
        return 1

    index_html, page = read("index.html"), read(gen.PAGE)
    if index_html is None or page is None:
        print(f"contact-check: {'index.html' if index_html is None else gen.PAGE} is missing{where}", file=sys.stderr)
        return 1
    try:
        want = gen.build(contact, catalog, index_html)
        have = gen.regions_of(page)
    except gen.GenError as e:
        print(f"contact-check: {e}{where}", file=sys.stderr)
        return 1

    stale = [name for name in gen.REGIONS if have[name] != want[name]]
    if stale:
        print(f"contact-check: contact data is stale against ~/Code/store/gen/contact.json{where} "
              f"({gen.PAGE}, region {', '.join(stale)}): {FIX}", file=sys.stderr)
        for name in stale:
            diff = list(difflib.unified_diff(have[name].splitlines(), want[name].splitlines(),
                                             f"{gen.PAGE} {name}", "regenerated", lineterm="", n=0))
            for line in diff[:12]:
                print(f"  {line[:200]}", file=sys.stderr)
            if len(diff) > 12:
                print(f"  ... {len(diff) - 12} more diff lines", file=sys.stderr)
        return 1
    print(f"contact-check: ok{where} ({len(want['data'].split('mailto:')) - 1} mailtos)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
