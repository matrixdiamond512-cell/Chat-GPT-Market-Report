#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: publish_stock_update.sh <commit-message> <path> [<path> ...]" >&2
  exit 2
fi

commit_message="$1"
shift

# A clean checkout is expected, but tolerate optional generated paths so one
# component can still publish its diagnostic status when an archive is absent.
git add -- "$@" 2>/dev/null || true
if git diff --cached --quiet; then
  echo "No stock data changes to publish."
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit -m "$commit_message"

# Several independent market collectors update data/stocks.json.  A single
# pull/rebase is racy: another collector can push after the fetch and before
# this push.  Retry the complete rebase/push transaction with backoff.
for attempt in 1 2 3 4 5; do
  if git pull --rebase origin main && git push origin HEAD:main; then
    echo "Published stock update on attempt ${attempt}."
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  if [ "$attempt" -lt 5 ]; then
    delay=$((attempt * 5))
    echo "Publish attempt ${attempt} lost a concurrent update; retrying in ${delay}s..."
    sleep "$delay"
  fi
done

echo "Failed to publish stock update after 5 attempts." >&2
exit 1
