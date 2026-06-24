#!/usr/bin/env bash
# ==============================================================================
# entrypoint.sh
# Runs every time the container starts (after the volume is mounted).
#
# 1. Clones / updates repos into the live /workspace volume.
# 2. Hands control to CMD (default: /bin/bash).
#
# Because this runs at container start — not during `docker build` — all cloned
# repos appear in the host-backed ./workspace folder on your machine.
# ==============================================================================

set -euo pipefail

echo "====> Running repo setup in /workspace..."
/usr/local/bin/clone_repos.sh

echo "====> Starting shell..."
echo "source /opt/ros/jazzy/setup.sh" >> ~/.bashrc
echo "source ~/venv/bin/activate" >> ~/.bashrc

# "$@" forwards the CMD value (/bin/bash by default), preserving exec so
# bash becomes PID 1 and signals work correctly.
exec "$@"
