#!/bin/bash
BRANCH=${1:-$(git rev-parse --abbrev-ref HEAD)}
git add .
git commit -m "message for the changes"
git push origin "$BRANCH"
