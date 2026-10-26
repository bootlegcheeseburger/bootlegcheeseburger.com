# Bootleg Cheeseburger - static site tasks
# Cloudflare Pages auto-deploys `main`, so pushing `main` is the deploy (`just push`).

# the shared shop recipes, through .blc (a gitignored link to the shop tooling,
# made by its post-checkout hook or `just tool-link`). They also export
# STORE_REPO, the store checkout every script here reads (scripts/store_path.py).
import? '.blc/just/core.just'

# serve the site locally with live-reload (vite HMR)
[group('main')]
run port="8000":
    npx vite --port {{port}}

# open the live site
[group('tool')]
tool-live:
    open https://bootlegcheeseburger.com

# open local preview with drafts visible (needs `just run` running)
[group('dev')]
dev-preview port="8000":
    open "http://localhost:{{port}}/?preview"

# short git status
[group('dev')]
dev-status:
    git status -s

# publish an app's EULA from $STORE_REPO/eula (header dropped, never hand-edited):
# eula/<app>.txt is the current text, eula/<app>/<id>.txt keeps every version,
# id = first 12 hex of the text's SHA-256 (the same rule as STORE's eula_version);
# also rewrites the app's tagged EULA_VERSION in index.html's STORE block, if any
[group('tool')]
tool-eula app:
    #!/usr/bin/env bash
    set -euo pipefail
    [[ "{{app}}" =~ ^[a-z0-9-]+$ ]] || { echo "bad app name: {{app}}" >&2; exit 1; }
    src="$STORE_REPO/eula/{{app}}.txt"
    [ -f "$src" ] || { echo "no $src" >&2; exit 1; }
    python3 -I scripts/eula-check.py --list | grep -qx "{{app}}" || { echo "{{app}}: not a published shared EULA (secret, or not eula \"shared\"); refusing" >&2; exit 1; }
    tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
    tail -n +3 "$src" > "$tmp"
    id=$(shasum -a 256 "$tmp" | cut -c1-12)
    kept="eula/{{app}}/$id.txt"
    mkdir -p "eula/{{app}}"
    if [ -e "$kept" ] && ! cmp -s "$tmp" "$kept"; then
        echo "$kept exists with different text; refusing" >&2; exit 1
    fi
    [ -e "$kept" ] || cp "$tmp" "$kept"
    cp "$tmp" "eula/{{app}}.txt"
    echo "{{app}} EULA $id: eula/{{app}}.txt, $kept"
    # the app's STORE block pin, if it has one: `EULA_VERSION: "<id>", // eula:{{app}}`
    pin='^([[:space:]]*EULA_VERSION: ")[0-9a-f]{12}(", // eula:{{app}})[[:space:]]*$'
    if grep -Eq "$pin" index.html && ! grep -Eq "EULA_VERSION: \"$id\", // eula:{{app}}" index.html; then
        sed -E -i '' "s#$pin#\\1$id\\2#" index.html
        echo "index.html: EULA_VERSION for {{app}} -> $id"
    fi

# share pages (<app>.html) and link-preview cards (assets/share/*.png) from the
# store catalog's taglines; no args = every public app plus the site card
[group('tool')]
tool-share-cards *apps:
    python3 -I scripts/share-cards.py {{apps}}

# the contact page's precomputed mailtos (contact.html, between its contact:gen
# markers) from $STORE_REPO/gen/contact.json; never hand-edit them
[group('tool')]
tool-contact:
    python3 -I scripts/contact-gen.py

# the license sentence in each app's buy fine print (index.html, between its
# license:gen markers) from $STORE_REPO/gen/apps.json; never hand-edit it
[group('tool')]
tool-license:
    python3 -I scripts/license-gen.py

# the "Free!" ribbon and the eyebrow's "Free" on each catalog app's card
# (index.html, between its free:gen badge/eyebrow markers) from the app's
# status in $STORE_REPO/gen/apps.json; never hand-edit them
[group('tool')]
tool-free:
    python3 -I scripts/free-gen.py

# app price labels (index.html, between its price:gen markers) and the STORE
# block's `// price:<app>` PRICE_LABEL and PRICE_ID (the id for its ENV) from
# $STORE_REPO/gen/apps.json; never hand-edit them
[group('tool')]
tool-price:
    python3 -I scripts/price-gen.py

# every store generator in one go: tool-eula for each app with a shared EULA in
# $STORE_REPO/gen/apps.json, tool-license, tool-price, tool-free, tool-contact,
# tool-share-cards (all), then dev-check; the one command after a store catalog change
[group('tool')]
tool-catalog:
    #!/usr/bin/env bash
    set -euo pipefail
    # shared EULAs minus secret apps (catalog `secret`, or unreleased with no app box)
    apps=$(python3 -I scripts/eula-check.py --list)
    for app in $apps; do just tool-eula "$app"; done
    just tool-license
    just tool-price
    just tool-free
    # tool-contact reads which apps are public from index.html: after the three above
    just tool-contact
    # slowest (headless Chromium): last
    just tool-share-cards
    just dev-check

# the gate: only catalog apps that are not secret reach the site (app boxes, nav
# links, icons, share pages and cards), and site EULAs, STORE EULA_VERSION, the
# contact page's mailtos, the app cards' "Free!" ribbons and eyebrows, the buy
# fine print's license sentence and the price labels and STORE PRICE_ID match
# the store checkout, $STORE_REPO (also .githooks/pre-push)
[group('dev')]
dev-check:
    python3 -I scripts/apps-check.py
    python3 -I scripts/eula-check.py
    python3 -I scripts/contact-check.py
    python3 -I scripts/free-check.py
    python3 -I scripts/license-check.py
    python3 -I scripts/price-check.py

# DNS / DNSSEC sanity check
[group('tool')]
tool-dns:
    @echo "A records:"  && dig +short bootlegcheeseburger.com
    @echo "DS (registry):" && dig +short DS bootlegcheeseburger.com
    @echo "header flags:"  && dig +dnssec bootlegcheeseburger.com | grep -E 'status:|flags:'
