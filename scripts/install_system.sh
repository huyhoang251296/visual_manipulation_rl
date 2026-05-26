#!/usr/bin/env bash
# ==============================================================================
# install_system.sh
# System-level package installation — called during `docker build`.
#
# HOW TO USE:
#   Add or remove apt packages in the PACKAGES list below.
#   For non-apt tools (pip, conda, cargo, etc.) use the sections at the bottom.
# ==============================================================================

set -euo pipefail

echo "====> Updating package index..."
apt-get update -y

# ------------------------------------------------------------------------------
# Core apt packages
# Add or remove entries here. One package per line for clean git diffs.
# ------------------------------------------------------------------------------
PACKAGES=(
    # Utilities
    curl
    wget
    git
    unzip
    zip
    vim
    nano
    htop
    tree
    ca-certificates
    gnupg
    lsb-release

    # Build tools
    build-essential
    cmake
    make

    # Networking
    net-tools
    iputils-ping

    # Python
    python3
    python3-pip
    python3-venv

    # Add more packages below 👇
    # nodejs
    # npm
    # default-jdk
)

echo "====> Installing apt packages..."
apt-get install -y --no-install-recommends "${PACKAGES[@]}"

# ------------------------------------------------------------------------------
# Python packages  (edit requirements.txt instead when possible)
# ------------------------------------------------------------------------------
# Uncomment and extend as needed:
# pip3 install --no-cache-dir \
#     numpy \
#     pandas \
#     requests

# ------------------------------------------------------------------------------
# Clean up to keep the image small
# ------------------------------------------------------------------------------
apt-get clean
rm -rf /var/lib/apt/lists/*

echo "====> System installation complete."
