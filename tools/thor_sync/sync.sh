#!/bin/bash
# Copy the onboard code and the real-robot documentation to the Thor's ~/Dev/lumi-wave.
#
#   tools/thor_sync/sync.sh            # code + docs (including docs/private) + tools + CLAUDE.md
#   tools/thor_sync/sync.sh --dry-run  # show what would change
#
# Only files tracked in git are copied from real/thor/, so local runtime files on the Thor (models, venv,
# logs, calibration, volume) are never touched. The simulation stays on the Mac.
# Restart nothing here: see "Deploying a change" in real/thor/README.md (never while the base drives).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOST="${THOR:-cutshion@192.168.10.240}"
DEST="Dev/lumi-wave"
SSH="ssh -o ControlPath=/tmp/thor-%r.sock"
RSYNC=(rsync -a --exclude .DS_Store --exclude __pycache__/ -e "$SSH")
[[ "${1:-}" == "--dry-run" ]] && RSYNC+=(--dry-run --itemize-changes)

cd "$REPO"
git ls-files real/thor | sed 's#^real/thor/##' > /tmp/lumi_thor_files.txt
"${RSYNC[@]}" --files-from=/tmp/lumi_thor_files.txt real/thor/ "$HOST:$DEST/"

# docs: everything about the real robot; on the Thor the code sits next to docs/, not in ../real/thor/
"${RSYNC[@]}" --delete --exclude SIMULATION.md docs/ "$HOST:$DEST/docs/"
"${RSYNC[@]}" --delete --exclude thor_sync/ tools/ "$HOST:$DEST/tools/"
"${RSYNC[@]}" tools/thor_sync/CLAUDE.md "$HOST:$DEST/CLAUDE.md"
if [[ "${1:-}" != "--dry-run" ]]; then
  $SSH "$HOST" "sed -i 's#\.\./\.\./docs/#docs/#g' $DEST/README.md"
  echo "synced to $HOST:$DEST"
fi
