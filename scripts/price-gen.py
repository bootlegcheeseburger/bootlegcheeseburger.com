#!/usr/bin/env python3
"""App price labels and Paddle price ids on the site, from the store catalog.

Reads <store>/gen/apps.json (owned by the store checkout, STORE_REPO: see
scripts/store_path.py) and rewrites, in index.html:
  - every region between a pair of markers
      <!-- price:gen <app> begin -->...<!-- price:gen <app> end -->
    with the app's price label, HTML-escaped, nothing else (no surrounding
    whitespace). The text around the markers is hand-written and left alone.
  - every tagged line of a STORE block (`var STORE = {` ... `};`)
      PRICE_LABEL: "<label>", // price:<app>
      PRICE_ID: "<id>", // price:<app>
    PRICE_LABEL is the app's price label; PRICE_ID is its
    `paddle.live.price_id` when the block's ENV is "production" and its
    `paddle.sandbox.price_id` when ENV is "sandbox".
The label is `price.amount` in `price.currency`: "29.00" USD is "$29",
"3.99" USD is "$3.99". Only USD is supported.

Fails (exit 1, writes nothing) on a region or tag naming an app with no
`price` (or, for PRICE_ID, no `paddle` price id for the block's ENV) in the
catalog, an unsupported currency or malformed amount, a block ENV other than
"production" or "sandbox", and on malformed markers or tags: a `price:gen`
comment that is not exactly `<!-- price:gen <app> begin|end -->`, an unpaired
or nested marker, an end naming another app than its begin, a PRICE_ID or
PRICE_LABEL line without exactly `// price:<app>` at its end, a price tag on
any other line, or a tagged PRICE_ID outside a STORE block.

Usage: python3 -I scripts/price-gen.py   (`just tool-price`)
scripts/price-check.py imports this file to regenerate and compare.
"""

import html
import importlib.util
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("store_path", ROOT / "scripts" / "store_path.py")
store_path = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store_path)
STORE = store_path.STORE
CATALOG = store_path.CATALOG
PAGE = "index.html"
MARKER = re.compile(r"<!-- price:gen ([a-z0-9-]+) (begin|end) -->")
LOOSE = re.compile(r"<!--[^>]*?price:gen")
KEY = re.compile(r"^\s*(PRICE_ID|PRICE_LABEL)\s*:")
TAGGED = re.compile(r'^\s*(PRICE_ID|PRICE_LABEL): "([^"\\]*)", // price:([a-z0-9-]+)\s*$')
MALTAG = re.compile(r"//.*price:")
STRAY = re.compile(r"//\s*price:\s*[a-z0-9-]")
BLOCK = re.compile(r"^[ \t]*var STORE = \{[^\n]*\n(.*?)^[ \t]*\};", re.M | re.S)
ENV = re.compile(r'^\s*ENV:\s*"([^"]*)"', re.M)
AMOUNT = re.compile(r"(0|[1-9][0-9]*)(\.[0-9]{2})?")
PRICE_ID = re.compile(r"pri_[a-z0-9]+")
SYMBOLS = {"USD": "$"}
ENVS = {"production": "live", "sandbox": "sandbox"}


class GenError(Exception):
    pass


def marker(app, end):
    return f"<!-- price:gen {app} {'end' if end else 'begin'} -->"


def tag_line(key, value, app):
    return f'{key}: "{value}", // price:{app}'


def load_catalog():
    if not STORE.is_dir():
        raise GenError(store_path.missing())
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GenError(f"cannot read {CATALOG} ({e}); {store_path.NEEDS}")


def label(catalog, app):
    """The app's price label, e.g. "$29" or "$3.99"."""
    entry = catalog.get(app)
    price = entry.get("price") if isinstance(entry, dict) else None
    if price is None:
        raise GenError(f"{app} has no price in the store catalog")
    amount = price.get("amount") if isinstance(price, dict) else None
    currency = price.get("currency") if isinstance(price, dict) else None
    if not isinstance(amount, str) or not AMOUNT.fullmatch(amount):
        raise GenError(f"{app}'s price.amount in the store catalog is {amount!r}, "
                       "not a string like \"29.00\"")
    if currency not in SYMBOLS:
        raise GenError(f"{app}'s price.currency in the store catalog is {currency!r}; "
                       f"the site renders only {', '.join(sorted(SYMBOLS))}: teach scripts/price-gen.py the currency")
    text = f"{Decimal(amount):,.2f}"
    if text.endswith(".00"):
        text = text[:-3]
    return SYMBOLS[currency] + text


def price_id(catalog, app, env):
    """The app's Paddle price id for a STORE block's ENV."""
    if env not in ENVS:
        raise GenError(f"the STORE block's ENV is {env!r}; price ids exist only for "
                       f"{' and '.join(repr(e) for e in ENVS)}")
    side = ENVS[env]
    entry = catalog.get(app)
    paddle = entry.get("paddle") if isinstance(entry, dict) else None
    if paddle is None:
        raise GenError(f"{app} has no paddle entry in the store catalog")
    sub = paddle.get(side) if isinstance(paddle, dict) else None
    pid = sub.get("price_id") if isinstance(sub, dict) else None
    if pid is None:
        raise GenError(f"{app} has no paddle.{side}.price_id in the store catalog (ENV {env!r})")
    if not isinstance(pid, str) or not PRICE_ID.fullmatch(pid):
        raise GenError(f"{app}'s paddle.{side}.price_id in the store catalog is {pid!r}, not pri_...")
    return pid


def want_tag(catalog, app, key, env):
    """What a tagged line's value should be."""
    if key == "PRICE_LABEL":
        return label(catalog, app)
    label(catalog, app)  # a PRICE_ID needs a catalog price too
    return price_id(catalog, app, env)


def regions_of(page):
    """[(app, start, end)] of every region in the page, in order: start..end is
    the text between the markers. GenError on malformed or unbalanced markers."""
    found = list(MARKER.finditer(page))
    if len(LOOSE.findall(page)) != len(found):
        raise GenError(f"{PAGE} has a `price:gen` comment that is not "
                       "`<!-- price:gen <app> begin -->` or `<!-- price:gen <app> end -->`")
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


def tags_of(page):
    """(tags, untagged) of the page's PRICE_ID / PRICE_LABEL lines.
    tags: [(app, key, env, start, end)], start..end the quoted value, env the
    enclosing STORE block's ENV (None for a PRICE_LABEL outside a block).
    untagged: [(line, key)] of key lines with no tag at all.
    GenError on a malformed or stray tag, or a PRICE_ID outside a STORE block."""
    blocks = []
    for b in BLOCK.finditer(page):
        envs = ENV.findall(b.group(1))
        blocks.append((b.start(), b.end(), envs))
    tags, untagged = [], []
    pos = 0
    for n, text in enumerate(page.split("\n"), 1):
        start, pos = pos, pos + len(text) + 1
        m = TAGGED.match(text)
        if m:
            key, app = m.group(1), m.group(3)
            block = next((b for b in blocks if b[0] <= start < b[1]), None)
            env = None
            if block is None:
                if key == "PRICE_ID":
                    raise GenError(f"{PAGE}:{n}: a tagged PRICE_ID is outside a `var STORE = {{` block, "
                                   "so it has no ENV")
            elif len(block[2]) != 1:
                if key == "PRICE_ID":
                    raise GenError(f"{PAGE}:{n}: the STORE block holding this PRICE_ID has "
                                   f"{len(block[2])} `ENV: \"...\"` lines, not one")
            else:
                env = block[2][0]
            tags.append((app, key, env, start + m.start(2), start + m.end(2)))
        elif KEY.match(text):
            key = KEY.match(text).group(1)
            if MALTAG.search(text):
                raise GenError(f"{PAGE}:{n}: a {key} line whose tag is not exactly "
                               f"`{tag_line(key, '...', '<app>')}`")
            untagged.append((n, key))
        elif STRAY.search(text):
            raise GenError(f"{PAGE}:{n}: a `// price:<app>` tag on a line that is not PRICE_ID or PRICE_LABEL")
    return tags, untagged


def untagged_message(line, key, where=""):
    return (f"{PAGE}:{line}{where}: {key} has no `// price:<app>` tag, so nothing writes or checks it: "
            f"write it as `{tag_line(key, '...', '<app>')}`, then run `just tool-price`")


def build(page, catalog):
    """The page with every region and tagged line rewritten from the catalog."""
    regions = regions_of(page)
    tags, untagged = tags_of(page)
    if untagged:
        raise GenError(untagged_message(*untagged[0]))
    edits = []
    for app, start, end in regions:
        try:
            edits.append((start, end, html.escape(label(catalog, app))))
        except GenError as e:
            raise GenError(f"{PAGE}:{page.count(chr(10), 0, start) + 1}: price:gen region: {e}")
    for app, key, env, start, end in tags:
        try:
            edits.append((start, end, want_tag(catalog, app, key, env)))
        except GenError as e:
            raise GenError(f"{PAGE}:{page.count(chr(10), 0, start) + 1}: {key} tagged price:{app}: {e}")
    for start, end, text in sorted(edits, reverse=True):
        page = page[:start] + text + page[end:]
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
        print(f"price-gen: {e}", file=sys.stderr)
        return 1
    regions = sorted({app for app, _, _ in regions_of(new)})
    tags = [f"{app} {key}" + (f" ({env})" if key == "PRICE_ID" else "") for app, key, env, _, _ in tags_of(new)[0]]
    if new != page:
        path.write_text(new, encoding="utf-8")
        print(f"price-gen: wrote {PAGE}")
    else:
        print(f"price-gen: {PAGE} already current")
    print(f"  regions: {', '.join(regions) or 'none'}")
    print(f"  tags: {', '.join(tags) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
