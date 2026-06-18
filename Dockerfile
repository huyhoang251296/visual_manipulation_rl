# ==============================================================================
# Docker Template for Student Projects
# ==============================================================================
# Default base image: Ubuntu 22.04
# Override at build time:
#   BASE_IMAGE=ubuntu:20.04 docker compose up --build
# ==============================================================================

ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

# Metadata
LABEL maintainer="your-email@example.com"
LABEL description="Student project workspace"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Berlin

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Local install (en_US.UTF-8 locale)
RUN apt update && apt install -y locales \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && export LANG=en_US.UTF-8

    
# Set working directory inside the container
WORKDIR /workspace

# ── System dependencies ───────────────────────────────────────────────────────
# Runs the shared system-install script so all package setup lives in one place
COPY requirements.txt /usr/local/bin/requirements.txt

COPY scripts/install_system.sh /tmp/install_system.sh
RUN chmod +x /tmp/install_system.sh && /tmp/install_system.sh && rm /tmp/install_system.sh

# ── Clone repos & entrypoint (run at container start, not at build time) ──────
# clone_repos.sh runs AFTER the volume is mounted so repos land in the
# host-backed /workspace, not in a hidden image layer.
COPY scripts/clone_repos.sh /usr/local/bin/clone_repos.sh
COPY scripts/entrypoint.sh  /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/clone_repos.sh /usr/local/bin/entrypoint.sh

# ── Python dependencies (optional) ─────────────────────────────────────────────
# COPY requirements.txt /tmp/requirements.txt
# RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ── Temporary: Add RUN command to install system packages before moving them to install_system.sh ────────
# For example:

# RUN apt update && apt install -y \
#     gedit \
#     git

RUN apt-get update && apt-get upgrade -y ros-jazzy-fastcdr ros-jazzy-rosidl-typesupport-fastrtps-cpp

# ── Entrypoint: clone repos into the live volume, then hand off to CMD ────────
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]