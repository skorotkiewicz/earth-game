# https://github.com/casey/just

[private]
default:
    @just --list

run *args:
    ./earth {{ args }}

web *args:
    ./earth web {{ args }}

check:
    python3 -m py_compile earth earth_core.py earth_web.py
    bash -n PKGBUILD

test: check
    python3 -m unittest -v

add-tag VERSION: test
    #!/usr/bin/env bash
    set -euo pipefail
    version="{{ VERSION }}"
    tag="v${version#v}"
    grep -qxF "pkgver=${tag#v}" PKGBUILD || { echo "Set pkgver=${tag#v} in PKGBUILD first" >&2; exit 1; }
    [ -z "$(git status --porcelain)" ] || { echo "Working tree is not clean" >&2; exit 1; }
    git tag -a "$tag" -m "Release $tag"
    git push --atomic origin main "$tag"

remove-tag VERSION:
    #!/usr/bin/env bash
    set -euo pipefail
    version="{{ VERSION }}"
    tag="v${version#v}"
    git tag -d "$tag"
    git push --delete origin "$tag"
