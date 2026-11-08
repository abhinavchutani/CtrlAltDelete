#!/usr/bin/env bash
# Build (and optionally push) the Field Radar image for Render: linux/amd64, API + web on one port.
#
#   scripts/build_image.sh <dockerhub-user>/field-radar:latest          # build into the local Docker
#   scripts/build_image.sh <dockerhub-user>/field-radar:latest --push   # build and push
#
# Needs out/serve.duckdb (make snapshot) and out/v2 (make v2) and the data pack under data/. Symlinks are resolved,
# so it works from a worktree. Nothing secret is copied; see .dockerignore.
set -euo pipefail
tag="${1:?usage: scripts/build_image.sh <image:tag> [--push]}"
mode="${2:---load}"
root="$(cd "$(dirname "$0")/.." && pwd)"
real() { python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"; }
pack="$(real "$root/data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026")"
v2="$(real "$root/out/v2")"
db="$(real "$root/out/serve.duckdb")"
for p in "$pack" "$v2" "$db"; do [ -e "$p" ] || { echo "missing: $p" >&2; exit 1; }; done
if [ -L "$root/out/serve.duckdb" ]; then echo "out/serve.duckdb is a symlink: copy the real file in first" >&2; exit 1; fi
docker buildx build --platform linux/amd64 --build-context pack="$pack" --build-context v2="$v2" \
  -t "$tag" "$mode" "$root"
