# Docker Deployment

JobRadar runs in Docker on a Linux host. This fork is deployed on
10.10.10.111 (debianmini) at port 8765.

## Quick Start

```bash
# Clone this fork to the host volume
git clone git@github.com:westteck/jobradar-docker.git /local/docker/jobradar/repo

# Create data directory
mkdir -p /local/docker/jobradar/data
touch /local/docker/jobradar/data/jobradar.db \
      /local/docker/jobradar/data/.resume_details.json \
      /local/docker/jobradar/data/.resume_profile.json

# Copy config (or edit in place - app re-reads on every scan)
cp /local/docker/jobradar/repo/config.yaml /local/docker/jobradar/config.yaml

# Place resume PDF
cp resume.pdf /local/docker/jobradar/resume.pdf

# Build and run
cd /local/docker/jobradar/repo
docker compose up -d --build
```

Web UI: `http://<host>:8765`
Settings: `http://<host>:8765/settings`

## Architecture

- **Base image**: `python:3.12-slim`
- **Network mode**: `host` - so Ollama at `localhost:11434` is reachable without code patches
- **Port**: 8765 (FastAPI web UI)
- **Config**: `/local/docker/jobradar/config.yaml` - bind-mounted, re-read on every scan (no restart needed for config changes)
- **Data**: `/local/docker/jobradar/data/` - SQLite DB + resume cache files, bind-mounted
- **Resume**: `/local/docker/jobradar/resume.pdf` - bind-mounted to `/app/resume.pdf`

## Config

Edit `/local/docker/jobradar/config.yaml` on the server, or use the settings
page at `/settings` in the web UI. The app re-reads config on every scan/API
call - no container restart needed.

Supported job board types (8): `greenhouse`, `lever`, `ashby`, `workable`,
`workday`, `oracle`, `atlassian`, `neogov`

### Adding a company

1. Open the settings page at `/settings`
2. Click "Add Company"
3. Enter the company **Name** and paste the **Job Listing URL** (e.g.
   `https://boards.greenhouse.io/figma` or
   `https://www.governmentjobs.com/careers/tuolumnecounty`)
4. The system auto-detects the board type and slug from the URL pattern
5. If the URL doesn't match a known board type, a dropdown appears to manually
   select the board type and enter the slug

Companies are listed alphabetically (A-Z) on the settings page.

## Settings Page

The settings page (`/settings`) provides a web UI for:

- **Companies**: Add, edit, delete companies. Auto-detect board type from URL.
  Companies sorted A-Z.
- **SMTP**: Configure email server for alerts and digests.
- **LLM/Provider**: Set the LLM provider and model for resume scoring.
- **Alerts**: Configure which companies to watch daily and the minimum score
  threshold.
- **Discovery**: Set keyword queries for global job discovery (remotive,
  arbeitnow, and governmentjobs.com global search).

## LLM Scoring

Set `provider: ollama` and `model: <ollama-model-name>` in config.yaml to
enable resume-based scoring.

Ollama runs on the host at `localhost:11434` - accessible from the container
via `network_mode: host`.

Default model: `gemma4:31b-cloud` (via Ollama membership, zero cost).

## Job Discovery

In addition to per-company scraping, JobRadar discovers jobs globally via
keyword search across three sources:

1. **Remotive** - remote job board API
2. **Arbeitnow** - job aggregator API
3. **NeoGov global search** - scrapes `governmentjobs.com/jobs?keywords=`
   HTML results across all government agencies

Discovery queries are configured in `config.yaml` under `discovery.queries`
or via the settings page.

## Remote/Hybrid Filter

The jobs grid has a work-type dropdown filter:

- **any work type** - shows all jobs (default)
- **remote only** - jobs with "remote" in location or description
- **hybrid only** - jobs with "hybrid" in location or description
- **remote or hybrid** - both

The filter checks both the `location` and `description` fields using
word-boundary matching. Works alongside the keyword search and company filter.

## Companies

This fork targets healthcare/medical employers for a practice administrator
job search:

- Oracle Recruiting Cloud: Adventist Health, Providence, Molina, Envision,
  Tenet, Loma Linda
- Workday: US Acute Care Solutions, Fresenius, Marathon Health, Centene,
  Elevance Health, Stryker, Sharp, Palomar
- NeoGov: Tuolumne County, and others via global search

Discovery queries: practice administrator, medical office manager, healthcare
administrator, privacy specialist, medical staff coordinator, practice manager

## Container Management

```bash
# Restart (picks up code changes in bind-mounted files)
docker restart jobradar

# View logs
docker logs jobradar -f --tail 50

# Run a scan
docker exec jobradar python -m jobradar scan

# Check DB stats
docker exec jobradar python -c "
import sqlite3; db=sqlite3.connect('/app/jobradar.db')
print(db.execute('SELECT COUNT(*) FROM jobs WHERE closed=0').fetchone()[0], 'open jobs')
"
```