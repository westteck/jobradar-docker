# Docker Deployment

JobRadar runs in Docker on server 10.10.10.111 (debianmini).

## Quick Start

```bash
# Clone this fork to the host volume
git clone git@github.com:westteck/jobradar-docker.git /local/docker/jobradar/repo

# Create data directory
mkdir -p /local/docker/jobradar/data
touch /local/docker/jobradar/data/jobradar.db \
      /local/docker/jobradar/data/.resume_details.json \
      /local/docker/jobradar/data/.resume_profile.json

# Copy config (or edit in place — app re-reads on every scan)
cp /local/docker/jobradar/repo/config.yaml /local/docker/jobradar/config.yaml

# Place resume PDF
cp resume.pdf /local/docker/jobradar/resume.pdf

# Build and run
cd /local/docker/jobradar/repo
docker compose up -d --build
```

## Architecture

- **Base image**: `python:3.12-slim`
- **Network mode**: `host` — so Ollama at `localhost:11434` is reachable without code patches
- **Port**: 8765 (FastAPI web UI)
- **Config**: `/local/docker/jobradar/config.yaml` — bind-mounted, re-read on every scan (no restart needed for config changes)
- **Data**: `/local/docker/jobradar/data/` — SQLite DB + resume cache files, bind-mounted
- **Resume**: `/local/docker/jobradar/resume.pdf` — bind-mounted to `/app/resume.pdf`

## Config

Edit `/local/docker/jobradar/config.yaml` on the server. The app re-reads it on every scan/API call — no container restart needed.

Supported job board types: `greenhouse`, `lever`, `ashby`, `workable`, `workday`, `oracle`, `atlassian`

## LLM Scoring

Set `provider: ollama` and `model: <ollama-model-name>` in config.yaml to enable resume-based scoring.

Ollama runs on the host at `localhost:11434` — accessible from the container via `network_mode: host`.

## Companies

This fork targets healthcare/medical employers for a practice administrator job search:
- Oracle Recruiting Cloud: Adventist Health, Providence, Molina, Envision, Tenet, Loma Linda
- Workday: US Acute Care Solutions, Fresenius, Marathon Health, Centene, Elevance Health, Stryker, Sharp, Palomar

Discovery queries: practice administrator, medical office manager, healthcare administrator, privacy specialist, medical staff coordinator, practice manager