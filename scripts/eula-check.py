#!/usr/bin/env python3
"""The site's published EULAs never drift from the store's rendered ones.

For every app whose entry in ~/Code/store/gen/apps.json has eula "shared":
  1. eula/<app>.txt is byte-equal to ~/Code/store/eula/<app>.txt minus its
     2-line header (`tail -n +3`);
  2. eula/<app>/<v>.txt holds that same text, v = the first 12 hex of its
     SHA-256 (STORE's eula_version).
  3. a STORE block's `EULA_VERSION: "<v>", // eula:<app>` line in index.html
     (the tag names the app; `just tool-eula <app>` rewrites it) holds that v. An
     EULA_VERSION line without the tag, or naming no shared app, fails too.
Older version files are never a violation. Reads only; never writes or deletes.
Every problem is reported in one run; exit 1 on any.

Usage: python3 -I scripts/eula-check.py [--rev REV]
  --rev REV  check the site files as committed at REV (the pre-push hook passes
             each pushed commit) instead of the working tree.
Run by `just dev-check` and .githooks/pre-push. The store is found through HOME.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.expanduser("~/Code/store")
KEY = re.compile(rb"^\s*EULA_VERSION\s*:")
TAGGED = re.compile(rb'^\s*EULA_VERSION: "([^"]*)", // eula:([a-z0-9-]+)\s*$')


def version(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()[:12]


def site_reader(rev):
    """Return read(path) -> bytes | None over the working tree or a commit."""
    if rev is None:
        def read(path):
            try:
                with open(os.path.join(SITE, path), "rb") as f:
                    return f.read()
            except FileNotFoundError:
                return None
        return read

    def read(path):
        r = subprocess.run(["git", "-C", SITE, "cat-file", "blob", f"{rev}:{path}"],
                           capture_output=True)
        return r.stdout if r.returncode == 0 else None
    return read


def main(argv):
    rev = None
    if argv[:1] == ["--rev"] and len(argv) == 2:
        rev = argv[1]
    elif argv:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2

    if not os.path.isdir(STORE):
        print("eula-check: needs ~/Code/store beside web (the store's EULAs are the source)", file=sys.stderr)
        return 1
    catalog = os.path.join(STORE, "gen", "apps.json")
    try:
        with open(catalog, encoding="utf-8") as f:
            apps = json.load(f)
    except (OSError, ValueError) as e:
        print(f"eula-check: cannot read ~/Code/store/gen/apps.json ({e}); needs ~/Code/store beside web", file=sys.stderr)
        return 1

    read = site_reader(rev)
    where = f" at {rev[:12]}" if rev else ""
    problems = []
    shared = sorted(a for a, e in apps.items() if isinstance(e, dict) and e.get("eula") == "shared")

    # STORE blocks: app -> [(line number, site EULA_VERSION)]
    pinned = {}
    for n, line in enumerate((read("index.html") or b"").split(b"\n"), 1):
        if not KEY.match(line):
            continue
        m = TAGGED.match(line)
        if not m:
            problems.append(f"index.html:{n}{where}: EULA_VERSION line has no `// eula:<app>` tag, "
                            "so nothing can check it: write it as `EULA_VERSION: \"<v>\", // eula:<app>`")
            continue
        app = m.group(2).decode()
        if app not in shared:
            problems.append(f"index.html:{n}{where}: EULA_VERSION is tagged eula:{app}, which has no shared EULA in ~/Code/store/gen/apps.json")
        pinned.setdefault(app, []).append((n, m.group(1).decode(errors="replace")))
    for app in shared:
        fix = f"run `just tool-eula {app}` and commit"
        try:
            with open(os.path.join(STORE, "eula", f"{app}.txt"), "rb") as f:
                lines = f.read().split(b"\n")
        except OSError:
            problems.append(f"~/Code/store/eula/{app}.txt is missing but apps.json gives {app} a shared EULA: fix the store")
            continue
        want = b"\n".join(lines[2:])  # tail -n +3
        v = version(want)

        cur = read(f"eula/{app}.txt")
        if cur is None:
            problems.append(f"eula/{app}.txt is missing{where}: {app} has a shared EULA in the store (store {v}): {fix}")
        elif cur != want:
            problems.append(f"eula/{app}.txt is stale against ~/Code/store/eula/{app}.txt "
                            f"(store {v}, site {version(cur)}){where}: {fix}")

        kept = read(f"eula/{app}/{v}.txt")
        if kept is None:
            problems.append(f"eula/{app}/{v}.txt is missing{where} (the versioned copy of store {v}): {fix}")
        elif kept != want:
            problems.append(f"eula/{app}/{v}.txt does not hold store {v}'s text{where} "
                            f"(it hashes to {version(kept)}): restore it from ~/Code/store/eula/{app}.txt, then {fix}")

        for n, site_v in pinned.get(app, []):
            if site_v != v:
                problems.append(f"EULA_VERSION for {app} is {site_v}, store is {v}: update the STORE block "
                                f"(index.html:{n}{where}; `just tool-eula {app}` rewrites it)")

    for p in problems:
        print(f"eula-check: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"eula-check: ok{where} ({', '.join(shared) or 'no shared EULAs'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
