#!/usr/bin/env bash
# Recompute CHECKSUMS for the per-arch release tarballs at the version
# pinned in VERSION, and rewrite the top-level CHECKSUMS file.
#
# Intended to run on a Renovate VERSION-bump PR (see
# .github/workflows/update-checksums.yml), but safe to run manually.
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="$(cat VERSION)"
BASE="https://github.com/anomalyco/opencode/releases/download/v${VERSION}"

ASSETS=(
  opencode-linux-x64.tar.gz
  opencode-linux-arm64.tar.gz
)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

{
  for ASSET in "${ASSETS[@]}"; do
    curl -fsSL -o "$TMP/$ASSET" "$BASE/$ASSET"
    printf '%s  %s\n' "$(sha256sum "$TMP/$ASSET" | cut -d' ' -f1)" "$ASSET"
  done
} > CHECKSUMS
