#!/bin/bash
# Publish the committed state of main to Gitea as one new commit on the clean `gitea` branch.
# Local main keeps the full history; Gitea only sees clean snapshots. Self-checks must pass first.
#   tools/gitea_push.sh "what changed"
set -euo pipefail
cd "$(dirname "$0")/.."
TOKEN_FILE=~/.config/lumi/gitea_token          # the owner's Gitea token, one line, chmod 600, never in git
MSG=${1:-"Update"}

[ "$(git rev-parse main^{tree})" = "$(git rev-parse gitea^{tree})" ] && { echo "nothing new to push"; exit 0; }
for t in tests/test_*.py; do
    .venv/bin/python "$t" > /dev/null 2>&1 || { echo "FAIL $t: not pushed"; exit 1; }
done
c=$(git commit-tree main^{tree} -p gitea -m "$MSG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
git -c credential.helper= -c http.extraHeader="Authorization: token $(cat "$TOKEN_FILE")" push origin "$c:main"
git branch -f gitea "$c"
echo "pushed $c"
