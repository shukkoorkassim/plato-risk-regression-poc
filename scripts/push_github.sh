#!/usr/bin/env bash
# scripts/push_github.sh — initialise git and push this project to GitHub.
#
#   ./scripts/push_github.sh https://github.com/<you>/plato-risk-regression-poc.git
#
# Uses your existing git credentials / PAT. The .env file is git-ignored so your
# Anthropic key is never pushed.
set -euo pipefail

REMOTE="${1:-}"
if [[ -z "$REMOTE" ]]; then
  echo "usage: $0 <github-repo-url>"
  exit 1
fi

cd "$(dirname "$0")/.."
git init -q
git add -A
git commit -q -m "Plato risk-based regression POC — Flow 1 (defect history) + Flow 2 (change driven)"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git push -u origin main
echo "Pushed to $REMOTE"
