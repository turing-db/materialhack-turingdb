#!/usr/bin/env bash
# Fetch the TuringDB Visualizer (pinned) and apply the Cupriavidus customization.
# Creates ./app/ (git-ignored): the upstream visualizer + the overlay in src/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/app"
VIS_REPO="${VIS_REPO:-https://github.com/turing-db/turingdb-visualizer.git}"
VIS_COMMIT="f6db08117a00ef822e147449cbb7b9bd39fdcdb7"

if [ ! -d "$APP/.git" ]; then
  echo "→ Cloning turingdb-visualizer…"
  git clone "$VIS_REPO" "$APP"
fi

echo "→ Pinning to $VIS_COMMIT"
( cd "$APP" && git fetch -q origin && git checkout -q "$VIS_COMMIT" )

echo "→ Applying Cupriavidus necator overlay (src/)…"
cp -R "$HERE/overlay/." "$APP/"

echo "→ npm install…"
( cd "$APP" && npm install )

echo "✓ Done — start the explorer with:  ./run.sh"
