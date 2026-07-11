# https://github.com/casey/just

[private]
default:
    @just --list

run *args:
    ./earth {{ args }}

web *args:
    ./earth web {{ args }}

fmt:
    ruff format earth earth_core.py earth_web.py test_earth.py

lint:
    ruff check earth earth_core.py earth_web.py test_earth.py

check: lint
    python3 -m py_compile earth earth_core.py earth_web.py
    bash -n PKGBUILD

test: check
    timeout 30 | python3 -m unittest -v

add-tag: test
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION=$(./earth --version)
    VERSION=${VERSION##* }
    git push origin main
    git tag -a "v${VERSION}" -m "Release v${VERSION}"
    git push origin "v${VERSION}"

# `just remove-tag v0.0.0` or `just remove-tag` (uses fzf)
remove-tag VERSION="":
    #!/usr/bin/env bash
    set -euo pipefail
    tag="{{ VERSION }}"
    [ -z "$tag" ] && tag=$(git tag | sort -V | fzf --prompt="Select tag to remove: ")
    [ -z "$tag" ] && echo "No tag selected" && exit 1
    git tag -d "$tag"
    git push --delete origin "$tag"
