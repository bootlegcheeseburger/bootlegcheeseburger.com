# Bootleg Cheeseburger - static site tasks
# Cloudflare Pages auto-deploys `main`, so pushing `main` is the deploy (`just push`).

import? '~/Code/blc/just/core.just'

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

# publish an app's EULA from ~/Code/store/eula (header dropped, never hand-edited):
# eula/<app>.txt is the current text, eula/<app>/<id>.txt keeps every version,
# id = first 12 hex of the text's SHA-256 (the same rule as STORE's eula_version);
# also rewrites the app's tagged EULA_VERSION in index.html's STORE block, if any
[group('tool')]
tool-eula app:
    #!/usr/bin/env bash
    set -euo pipefail
    [[ "{{app}}" =~ ^[a-z0-9-]+$ ]] || { echo "bad app name: {{app}}" >&2; exit 1; }
    src="$HOME/Code/store/eula/{{app}}.txt"
    [ -f "$src" ] || { echo "no $src" >&2; exit 1; }
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
# markers) from ~/Code/store/gen/contact.json; never hand-edit them
[group('tool')]
tool-contact:
    python3 -I scripts/contact-gen.py

# the gate: site EULAs, STORE EULA_VERSION and the contact page's mailtos match
# ~/Code/store (also .githooks/pre-push)
[group('dev')]
dev-check:
    python3 -I scripts/eula-check.py
    python3 -I scripts/contact-check.py

# DNS / DNSSEC sanity check
[group('tool')]
tool-dns:
    @echo "A records:"  && dig +short bootlegcheeseburger.com
    @echo "DS (registry):" && dig +short DS bootlegcheeseburger.com
    @echo "header flags:"  && dig +dnssec bootlegcheeseburger.com | grep -E 'status:|flags:'
