#!/usr/bin/env bash
# ==============================================================================
# clone_repos.sh
# Clones all project repositories into /workspace/src/.
# Called by entrypoint.sh at container start, so repos land inside the
# host-mounted volume (/workspace) and are visible on your machine.
#
# HOW TO USE:
#   Add entries to the REPOS section below. Each entry is:
#     clone_repo "https://github.com/owner/repo-name.git" ["branch"]
#
#   For private repos, export GITHUB_TOKEN in your shell before starting:
#     export GITHUB_TOKEN=ghp_xxx
#     docker compose up -d
#   Then use: "https://${GITHUB_TOKEN}@github.com/owner/private-repo.git"
# ==============================================================================

set -euo pipefail

mkdir -p /workspace/src

GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ------------------------------------------------------------------------------
# Helper: clone_repo <url> [branch]
# Clones into a subdirectory named after the repo. Pulls if already present.
# ------------------------------------------------------------------------------
clone_repo() {
    local url="$1"
    local branch="${2:-}"
    local repo_name
    repo_name=$(basename "$url" .git)
    local target="/workspace/src/$repo_name"

    if [[ -d "$target/.git" ]]; then
        echo "  [pull]  $repo_name — already exists, pulling latest..."
        git -C "$target" pull --ff-only
        return
    fi

    echo "  [clone] $repo_name${branch:+ @ $branch}..."
    if [[ -n "$branch" ]]; then
        git clone --depth 1 --branch "$branch" "$url" "$target"
    else
        git clone --depth 1 "$url" "$target"
    fi
}

# ------------------------------------------------------------------------------
# REPOS — add your repositories here 👇
# Format: clone_repo "<repo-url>" ["<branch>"]
# ------------------------------------------------------------------------------

# Example public repo:
# clone_repo "https://github.com/your-org/project-starter.git"
# clone_repo "https://github.com/your-org/shared-utils.git" "main"

# Example private repo (requires GITHUB_TOKEN exported in your shell):
# clone_repo "https://${GITHUB_TOKEN}@github.com/your-org/private-repo.git"

# ── Add your repos below ──────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────

echo "====> Workspace src contents:"
ls -la "/workspace/src/"
