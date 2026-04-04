#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

source .venv/bin/activate

OUTPUT=$(bash should_work.sh 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "should_work.sh failed with exit code $EXIT_CODE"
    echo "$OUTPUT"
    exit 1
fi

SCHEDULE="output/schedule.json"
if [ ! -f "$SCHEDULE" ]; then
    echo "schedule.json not found at $SCHEDULE"
    exit 1
fi

rcj-planner validate "$SCHEDULE"
VALIDATE_CODE=$?

if [ $VALIDATE_CODE -ne 0 ]; then
    echo "rcj-planner validate failed with exit code $VALIDATE_CODE"
    exit 1
fi

echo "All checks passed."
