#!/usr/bin/env bash
# watch-git.sh
# Usage: ./watch-git.sh /absolute/path/to/your/expo-repo

REPO_PATH="${1:?Usage: ./watch-git.sh /path/to/repo}"

if [ ! -d "$REPO_PATH/.git" ]; then
  echo "❌ $REPO_PATH is not a git repo"
  exit 1
fi

cd "$REPO_PATH" || exit 1
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "Watching $REPO_PATH (branch: $BRANCH)..."

while true; do
  git fetch origin "$BRANCH" --quiet
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse "origin/$BRANCH")

  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date '+%H:%M:%S') New commit detected, pulling..."
    git pull --ff-only origin "$BRANCH"

    if git diff --name-only "$LOCAL" "$REMOTE" | grep -q "package.json"; then
      echo "⚠️  package.json changed — run npm install and restart Expo."
    fi
  fi
  sleep 20
done
