# Bootleg Cheeseburger - static site tasks
# Cloudflare Pages auto-deploys `main`, so pushing `main` is the deploy (`just push`).

# serve the site locally with live-reload (vite HMR)

import? '~/Code/blc/just/core.just'

serve port="8000":
    npx vite --port {{port}}

# open the live site
live:
    open https://bootlegcheeseburger.com

# open local preview with drafts visible (needs `just serve` running)
preview port="8000":
    open "http://localhost:{{port}}/?preview"

# short git status
status:
    git status -s

# publish an app's EULA from ~/Code/store/eula (header dropped, never hand-edited):
# eula/<app>.txt is the current text, eula/<app>/<id>.txt keeps every version,
# id = first 12 hex of the text's SHA-256 (the same rule as STORE's eula_version)
eula app:
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

# DNS / DNSSEC sanity check
dns:
    @echo "A records:"  && dig +short bootlegcheeseburger.com
    @echo "DS (registry):" && dig +short DS bootlegcheeseburger.com
    @echo "header flags:"  && dig +dnssec bootlegcheeseburger.com | grep -E 'status:|flags:'
