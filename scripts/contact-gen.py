#!/usr/bin/env python3
"""The contact page's data, precomputed from the store's contact templates.

Reads ~/Code/store/gen/contact.json (the templates, owned by ~/Code/store),
~/Code/store/gen/apps.json (display names) and index.html (which apps are
public: an article.showcase without the draft class). Offers an app only when
it is public here and has an entry in contact.json `apps`.

It renders one mailto for every valid choice:
  - each public app with each kind in its list (`<app>/<kind>`);
  - each shop-scope kind with no app (`/<kind>`).
and writes them into contact.html between its `contact:gen` markers:
  - `fallback`: the no-JS list of shop-level mailtos;
  - `data`: the JSON the page script reads (kinds, apps, mailtos).
The browser does no templating; it only picks a precomputed URL.

Rendering matches blc-kit's blc-contact (crates/blc-contact, 1a971c3):
{app} is the app's display name; {version} {build} {macos} {serial_last4}
and any unknown placeholder are blank. An empty version writes the subject
tag as `[App]`; with no app the site also drops the tag, `[{app}] `, so the
subject starts with the bare `Kind: ` (blc-inbox reads all three forms).
Subject and body are percent-encoded per RFC 6068 (every byte outside the
unreserved set, a space as %20, a line break as %0D%0A). A mailto over
`mailto_max` characters is an error, never truncated.

Usage: python3 -I scripts/contact-gen.py   (`just tool-contact`)
scripts/contact-check.py imports this file to regenerate and compare.
"""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = Path.home() / "Code/store"
CONTACT = STORE / "gen/contact.json"
CATALOG = STORE / "gen/apps.json"
PAGE = "contact.html"
REGIONS = ("fallback", "data")
UNRESERVED = re.compile(rb"[A-Za-z0-9._~-]")


class GenError(Exception):
    pass


def marker(name, end):
    return f"<!-- contact:gen {name} {'end' if end else 'begin'} -->"


# ---- blc-contact's rendering, line for line ----

def subject_tag(subject, version, app):
    """With no version the tag `[{app} {version}]` reads `[{app}]`; with no app
    either, the site drops the whole tag and its space."""
    if not version:
        subject = subject.replace(" {version}]", "]", 1)
        if not app and subject.startswith("[{app}] "):
            subject = subject[len("[{app}] "):]
    return subject


def fill(text, fields):
    """One pass over `{name}` spans (no braces inside): known names take their
    field, any other becomes a blank. Filled values are not scanned again."""
    out = []
    rest = text
    while (i := rest.find("{")) != -1:
        out.append(rest[:i])
        after = rest[i + 1:]
        m = re.search(r"[{}]", after)
        if m and m.group() == "}":
            out.append(fields.get(after[:m.start()], ""))
            rest = after[m.start() + 1:]
        else:
            out.append("{")
            rest = after
    out.append(rest)
    return "".join(out)


def encode(s):
    return "".join(chr(b) if UNRESERVED.fullmatch(bytes([b])) else f"%{b:02X}" for b in s.encode("utf-8"))


def mailto(template, app_name, limit):
    fields = {"app": app_name}  # every other placeholder is blank on the site
    subject = fill(subject_tag(template["subject"], "", app_name), fields)
    subject = subject.replace("\r", " ").replace("\n", " ")
    body = fill(template["body"], fields).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    url = f"mailto:{template['to']}?subject={encode(subject)}&body={encode(body)}"
    if len(url) > limit:
        raise GenError(f"{app_name or 'no app'}: a {len(url)}-character mailto, over mailto_max {limit}")
    if "[]" in subject or "[ ]" in subject:
        raise GenError(f"{app_name or 'no app'}: subject {subject!r} keeps an empty tag")
    return url


# ---- inputs ----

def public_apps(index_html):
    """Slugs of the non-draft app boxes in index.html, in page order."""
    apps = []
    for m in re.finditer(r"<article\s([^>]*)>", index_html):
        attrs = m.group(1)
        idm = re.search(r'\bid="app-([a-z0-9-]+)"', attrs)
        cls = re.search(r'\bclass="([^"]*)"', attrs)
        if not idm or not cls:
            continue
        classes = cls.group(1).split()
        if "showcase" in classes and "draft" not in classes:
            apps.append(idm.group(1))
    return apps


def load_store():
    if not STORE.is_dir():
        raise GenError("needs ~/Code/store beside web (~/Code/store/gen/contact.json is the source)")
    try:
        contact = json.loads(CONTACT.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GenError(f"cannot read the store's gen files ({e}); needs ~/Code/store beside web")
    return contact, catalog


# ---- output ----

def build(contact, catalog, index_html):
    """{region: text} for contact.html, from the store files and index.html."""
    try:
        limit = int(contact["mailto_max"])
        kinds = contact["kinds"]
        app_kinds = contact["apps"]
        for k, t in kinds.items():
            for key in ("label", "scope", "to", "subject", "body"):
                if not isinstance(t.get(key), str):
                    raise GenError(f"kind {k} has no string {key}")
            if t["scope"] not in ("app", "shop"):
                raise GenError(f"kind {k} has scope {t['scope']!r}")
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise GenError(f"contact.json is not the expected shape ({e!r})")

    public = set(public_apps(index_html))
    apps = []
    for slug, ks in app_kinds.items():  # contact.json order
        if slug not in public:
            continue
        name = (catalog.get(slug) or {}).get("name")
        if not isinstance(name, str) or not name:
            raise GenError(f"{slug} has no name in ~/Code/store/gen/apps.json")
        unknown = [k for k in ks if k not in kinds]
        if unknown:
            raise GenError(f"{slug} lists unknown kinds {unknown}")
        apps.append({"id": slug, "name": name, "kinds": [k for k in kinds if k in ks]})

    urls = {}
    for a in apps:
        for k in a["kinds"]:
            urls[f"{a['id']}/{k}"] = mailto(kinds[k], a["name"], limit)
    shop = [k for k, t in kinds.items() if t["scope"] == "shop"]
    for k in shop:
        urls[f"/{k}"] = mailto(kinds[k], "", limit)

    data = {
        "kinds": [{"id": k, "label": t["label"], "scope": t["scope"], "to": t["to"]} for k, t in kinds.items()],
        "apps": apps,
        "mailto": urls,
    }
    blob = json.dumps(data, indent=2, ensure_ascii=True).replace("</", "<\\/")
    data_region = f'\n    <script type="application/json" id="contact-data">\n{blob}\n    </script>\n    '

    items = "".join(
        f'\n          <li><a href="{html.escape(urls["/" + k])}">{html.escape(kinds[k]["label"])}</a>'
        f' <span class="to">{html.escape(kinds[k]["to"])}</span></li>'
        for k in shop
    )
    return {"fallback": items + "\n          ", "data": data_region}


def regions_of(page):
    """{region: text between its markers} of contact.html's text; GenError if a
    marker pair is missing or repeated."""
    out = {}
    for name in REGIONS:
        b, e = marker(name, False), marker(name, True)
        if page.count(b) != 1 or page.count(e) != 1 or page.index(b) > page.index(e):
            raise GenError(f"{PAGE} needs one `{b}` ... `{e}` pair")
        out[name] = page[page.index(b) + len(b):page.index(e)]
    return out


def splice(page, regions):
    regions_of(page)  # validates the markers
    for name, text in regions.items():
        b, e = marker(name, False), marker(name, True)
        page = page[:page.index(b) + len(b)] + text + page[page.index(e):]
    return page


def main(argv):
    if argv:
        print(__doc__.strip().split("\n\n")[-2], file=sys.stderr)
        return 2
    try:
        contact, catalog = load_store()
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        regions = build(contact, catalog, index_html)
        path = ROOT / PAGE
        page = path.read_text(encoding="utf-8")
        new = splice(page, regions)
    except GenError as e:
        print(f"contact-gen: {e}", file=sys.stderr)
        return 1
    if new != page:
        path.write_text(new, encoding="utf-8")
        print(f"contact-gen: wrote {PAGE}")
    else:
        print(f"contact-gen: {PAGE} already current")
    data = json.loads(regions["data"].split(">", 1)[1].rsplit("</script>", 1)[0])
    print(f"  {len(data['mailto'])} mailtos; apps: {', '.join(a['id'] for a in data['apps'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
