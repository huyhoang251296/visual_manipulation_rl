# 🐳 Student Project Docker Template

A ready-to-use Docker workspace for student projects. Clone this repo, configure your packages and repos, and get everyone on the same environment in minutes.

---

## 📁 File Structure

```
.
├── Dockerfile                  # Container definition (Ubuntu 22.04 default)
├── docker-compose.yml          # Build and run with volume mount
├── .dockerignore
├── .gitignore
├── workspace/                  # ← your local files, mounted into the container
└── scripts/
    ├── install_system.sh       # All apt / pip packages installed at build time
    └── clone_repos.sh          # GitHub repos cloned into /workspace at build time
```

---

## 🚀 Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running (Docker Compose is included)

### 1 — Clone this template and install Docker

```bash
git clone https://github.com/your-org/your-template.git my-project
cd my-project
```

Install Docker if Docker doesn't already exist on your PC.

```bash
source scripts/install_docker.sh
```

### 2 — Configure your workspace

| File | What to edit |
|------|-------------|
| `docker-compose.yml` | Update `image:` to your application name (e.g., `my-app:latest`) and update `container_name:` to your container name (e.g., `my-app-workspace`) |
| `scripts/install_system.sh` | Add apt packages, pip packages, or other tools |
| `scripts/clone_repos.sh` | Add GitHub repos to clone into the workspace |

### 3 — Build & run

On Ubuntu, to allow your Docker to access the GUI
```
xhost +local:docker || true
```

```bash
# Build the container with package installation and cloning repositories
docker compose up --build -d

# open a shell inside the running container:
docker compose exec workspace bash
```

Your local `./workspace/` folder is mounted at `/workspace` inside the container — changes sync both ways instantly.

---

## ⚙️ Changing the Base Image

The default base image is **`ubuntu:22.04`**. Override it without editing any file:

```bash
BASE_IMAGE=ubuntu:20.04 docker compose up --build
```

Any image available on [Docker Hub](https://hub.docker.com/) works as a base.

---

## 🔒 Private GitHub Repositories
 
Access private repos by adding an SSH key to your GitHub account and mounting it into the container.
 
### 1 — Generate an SSH key (skip if you already have one)
 
```bash
ssh-keygen -t ed25519
# Press Enter to accept the default path (~/.ssh/id_ed25519)
# Set a passphrase or leave empty
```
 
### 2 — Add the public key to GitHub
 
Copy your public key:
```bash
cat ~/.ssh/id_ed25519.pub
```
 
Then go to **GitHub → Settings → SSH and GPG keys → New SSH key**, paste it in, and save.
 
### 3 — Mount your SSH key into the container
 
Uncomment the SSH volume lines in `docker-compose.yml`:
 
```yaml
volumes:
  - ./workspace:/workspace
  - ~/.ssh:/root/.ssh:ro   # mounts your host SSH keys as read-only
```
 
### 4 — Use SSH URLs in `clone_repos.sh`
 
```bash
clone_repo "git@github.com:your-org/private-repo.git"
```
 
> **Note:** Your SSH key is mounted read-only at runtime and is never copied into the image.
 
---
 


---

## 💾 Volume / Persistent Storage

The `workspace/` directory on your host machine is bind-mounted into the container at `/workspace`. This means:

- **Your files survive container restarts** — nothing is lost when you stop the container.
- **Edit locally, run inside Docker** — use your favourite editor on your machine while code executes in the container.
- The `workspace/` folder is git-ignored so each student's work stays local.

---

## 🛠️ Common Commands

```bash
# Rebuild after changing Dockerfile or scripts
docker compose up --build -d

# Open a new shell in a running container
docker compose exec workspace bash

# Stop the container
docker compose down

# Remove the image, change student-project to your "my-app" image name
docker rmi student-project:latest
```

---

## 📝 Customisation Checklist

- [ ] Edit `scripts/install_system.sh` — add your project's apt/pip packages
- [ ] Edit `scripts/clone_repos.sh` — list the repos students need
- [ ] Update the `LABEL maintainer` line in the `Dockerfile`
- [ ] Set a meaningful `IMAGE_NAME` in `docker-compose.yml`
- [ ] Clone this README.md to DockerInstruction.md
- [ ] Update this README with project-specific instructions
