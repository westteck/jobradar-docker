# Job Radar (Dockerized Fork)

Watches company job boards, scores every opening against your resume, and
emails you when something worth applying to shows up.

![grid](docs/grid.png)

This is a Dockerized fork of [suvamneog/jobradar](https://github.com/suvamneog/jobradar)
(MIT) extended with a settings page, auto-detect board type, government jobs
search, and remote/hybrid filtering.

## What it does

- **Finds new openings.** Every job gets a stable id, so "new" means new.
- **Notices when jobs close.** A posting that disappears is marked dead and hidden.
- **Ranks against your resume.** 0-10 with a reason, from an LLM that reads the
  job description.
- **Daily alerts** for a shortlist of companies - email plus a desktop notification.
- **Weekly digest** every Monday, ranked.
- **A local web UI** to search and filter everything.
- **Settings page** to manage companies, SMTP, LLM config, alerts, and discovery
  keywords from the browser - no config file editing required.
- **Auto-detect board type** from the job listing URL - paste a URL, the system
  figures out the board and slug automatically.
- **Remote/hybrid filter** on the jobs grid - narrow results to remote-only,
  hybrid-only, or either.
- **Global government jobs search** across all governmentjobs.com agencies via
  keyword search, in addition to per-agency scraping.

![email](docs/email.png)

## Supported Job Boards (8 types)

| Board | URL pattern | Auto-detect |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/{slug}` | Yes |
| Lever | `jobs.lever.co/{slug}` | Yes |
| Ashby | `jobs.ashbyhq.com/{slug}` | Yes |
| Workable | `apply.workable.com/{slug}` | Yes |
| Workday | `{tenant}.{wdN}.myworkdayjobs.com/{site}` | Yes |
| Oracle | `{host}.oraclecloud.com/.../sites/{site}` | Yes |
| Atlassian | `atlassian.com/...careers` | Yes |
| NeoGov | `governmentjobs.com/careers/{slug}` | Yes |

If a URL doesn't match any known board type, a manual fallback lets you pick
the board type and enter the slug by hand.

## Docker Deployment

Runs in Docker on a Linux host. See [DOCKER.md](DOCKER.md) for full details.

```bash
git clone git@github.com:westteck/jobradar-docker.git
cd jobradar-docker
docker compose up -d --build
```

Web UI at `http://localhost:8765`, settings at `http://localhost:8765/settings`.

### Key differences from upstream

- **Docker**: Runs in a container with `network_mode: host` so local Ollama
  is reachable without code patches.
- **Config**: Bind-mounted `config.yaml` - edit on the host, app re-reads on
  every scan, no restart needed.
- **Data**: SQLite DB and resume cache bind-mounted to `/local/docker/jobradar/data/`.
- **LLM**: Uses Ollama (local or cloud) instead of xkiro. Default model:
  `gemma4:31b-cloud`.
- **Settings page**: Full web UI for managing companies, SMTP, LLM/provider
  config, alert rules, and discovery keywords. Companies sorted A-Z.
- **Auto-detect**: Paste any job board URL on the settings page and the system
  identifies the board type and slug via regex patterns.
- **NeoGov**: governmentjobs.com support - both per-agency scraping (via
  `loadJobsOnMaps` API) and global keyword search (via `/jobs?keywords=` HTML
  parsing) across all agencies.
- **Remote/hybrid filter**: Dropdown on the jobs grid to filter by work type.

## Why it isn't just keyword matching

Two rules run in code, not in the prompt, because a model asked nicely will
comply inconsistently:

**Seniority.** A Senior/Staff/Principal title caps at 3/10 however well the
skills match. Without this, senior roles held 31 of the top 100 slots and the
first junior role sat at position #67 - the jobs a new graduate could actually
get were buried under the ones they could not.

**Relevance.** A role weak on both skills and domain caps at 3/10. Otherwise a
branch-office internship scores 8/10 for a developer purely because it is an
internship.

Both are arithmetic on data already stored, so `recap` re-applies them for free.

## Configuration

Edit `config.yaml` on the host (bind-mounted, no restart needed) or use the
settings page at `/settings`:

```yaml
companies:
  - { name: 'Adobe', board: workday, slug: 'adobe/wd5/external_experienced' }

alerts:
  companies: [Adobe, Oracle, Atlassian]
  min_score: 6

llm:
  provider: ollama
  model: gemma4:31b-cloud

discovery:
  queries: [practice administrator, remote, healthcare administrator]
```

## Commands

```bash
docker exec jobradar python -m jobradar scan     # fetch, diff, score
docker exec jobradar python -m jobradar alert    # check shortlist, alert
docker exec jobradar python -m jobradar digest   # send weekly email
docker exec jobradar python -m jobradar recap    # re-apply scoring rules
docker exec jobradar python -m jobradar list     # week's finds in terminal
```

Or use the web UI at `http://localhost:8765` for scanning and browsing.

## Token budget

Jobs are scored 25 per request with compact positional replies. A full scan
costs about 340K tokens. After that only new postings are scored, which is a
few thousand a week. With Ollama cloud models, cost is zero.

## Tests

```bash
for t in tests/test_*.py; do ./.venv/bin/python "$t"; done
```

## Notes

Forked from [suvamneog/jobradar](https://github.com/suvamneog/jobradar) (MIT).

Scores are a sort order, not a verdict - a 4/10 is still worth a glance.

MIT