# Job Alert Extraction & CSV Export System

Monitors your Gmail job-alert emails (LinkedIn, Indeed, Wellfound, ...),
extracts job title/company/location/URL, extracts the **actual job posting
date** separately from the email's received date, classifies jobs against
your configured categories, deduplicates them, and (in a later phase)
exports matches to CSV.

**Scope boundary:** this system reads Gmail and produces structured job
data. It does **not** scrape job sites, open a browser, fill application
forms, upload resumes, or submit applications. That is out of scope by
design.

## What's implemented

- **Phase 0 — Scaffolding:** FastAPI + MySQL + Redis + Celery/Beat backend,
  Vue 3 + Vite + TS + Tailwind + Pinia frontend, Docker Compose, tooling.
- **Phase 1 — Gmail Ingestion:** OAuth2 (`gmail.readonly` only), encrypted
  token storage, last-24-hour lookback search, processed-email dedup,
  email normalization, scheduled sync via Celery Beat.
- **Phase 2 — Platform Parsers:** `JobPlatformParser` contract + registry,
  LinkedIn/Indeed/Wellfound parsers, GenericParser fallback.
- **Phase 3 — Date & URL Extraction:** `JobPostedDateExtractor` (explicit
  dates, "N hours/days ago", "yesterday" — never fabricated), `UrlExtractor`
  (anchor-text + domain scoring), SSRF-safe `RedirectResolver`.
- **Phase 4 — Classification:** database-driven `JobCategory` /
  `JobCategoryKeyword`, `RuleBasedClassifier` (word-boundary matching,
  negative keywords), seeded with PHP/Laravel/Backend/AI/LLM/Python/
  OpenCart/Machine Learning/Generative AI.
- **Phase 5 — Deduplication & Persistence:** `JobFingerprintService`
  (canonical-URL based, strips tracking params), `JobRepository` (dedup by
  fingerprint, never overwrites an existing job), `Job` /
  `job_category_pivot` / `ProcessingEvent` models, `JobProcessingService`
  tying parse → classify → dedupe → persist together.

**Not yet built:** CSV export & filters (Phase 6), the dashboard UI beyond
the Phase 0 shell (Phase 7), and production scheduling/hardening (Phase 8).
The `frontend/` app currently only shows a backend-connectivity check.

**49 backend tests pass**, including an end-to-end test proving the same
job arriving via two different emails is persisted only once.

---

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, MySQL, Redis, Celery + Celery Beat
- **Frontend:** Vue 3, Vite, TypeScript, Tailwind CSS v4, Pinia, Vue Router, Axios
- **Gmail:** Google OAuth 2.0, `gmail.readonly` scope only

---

## Setting this up in WSL — step by step

Do this from a fresh WSL install or an existing one; skip steps you've
already done. Everything happens **inside the WSL Ubuntu shell**, not
PowerShell, except step 1.

### 1. Install WSL + Ubuntu (PowerShell, if not already installed)

```powershell
wsl --install -d Ubuntu-24.04
```

Reboot if prompted, then open "Ubuntu 24.04" from the Start menu and finish
the first-run username/password setup.

### 2. Install system packages (inside WSL)

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv build-essential \
    default-libmysqlclient-dev pkg-config unzip curl
```

### 3. Install Node via nvm (inside WSL — do not use Windows' Node)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 22
node --version   # should print v22.x
```

### 4. Install Docker

The simplest path: install **Docker Desktop for Windows**, then in Docker
Desktop go to **Settings → Resources → WSL Integration** and enable it for
your Ubuntu distro. Back in the WSL shell:

```bash
docker --version
docker compose version
```

Both should now work without installing anything else inside WSL.

(Alternative: install Docker Engine natively inside WSL2 following
Docker's official Ubuntu instructions, if you'd rather not run Docker
Desktop at all.)

### 5. Put the project inside the WSL filesystem — not `/mnt/c/...`

This matters: files under `/mnt/c/...` are Windows files accessed through a
9P network mount, which is dramatically slower for `node_modules`,
`pip install`, and Docker bind mounts. Keep the project on the Linux side:

```bash
mkdir -p ~/projects
cd ~/projects
unzip /mnt/c/Users/<your-windows-username>/Downloads/job-automation.zip
cd job-automation
```

(Adjust the path to wherever you downloaded the zip on Windows — it's
visible from WSL under `/mnt/c/...`, you're just copying it *out* of there,
not working from it in place.)

### 6. Configure environment variables

```bash
cp .env.example .env
nano .env   # or your editor of choice
```

At minimum set `SECRET_KEY` to something random. Leave `GOOGLE_CLIENT_ID`
and `GOOGLE_CLIENT_SECRET` blank for now — you only need those once you get
to connecting a real Gmail account (see below).

### 7. Start MySQL, Redis, the API, and Celery

```bash
docker compose up --build
```

Leave this running in its own terminal tab (WSL terminals support multiple
tabs — use whatever terminal app you're running, e.g. Windows Terminal).
The first build takes a few minutes.

### 8. Run database migrations

In a **second** WSL terminal:

```bash
cd ~/projects/job-automation/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

This creates all tables and seeds the initial platforms (LinkedIn, Indeed,
Wellfound) and categories (PHP, Laravel, Backend, AI, LLM, Python,
OpenCart, Machine Learning, Generative AI).

### 9. Verify the backend

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/db
```

WSL2 automatically forwards `localhost` ports to Windows, so
`http://localhost:8000` also works directly from a Windows browser.

### 10. Run the test suite and quality checks

Still inside `backend/` with `.venv` activated:

```bash
pytest
ruff check .
black --check .
mypy app
```

All should pass — this is the same command set used to verify this build.

### 11. Frontend

In a third terminal:

```bash
cd ~/projects/job-automation/frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your Windows browser. It should show
"Connected" under Backend connection.

### 12. Connect a Gmail account (needed to actually pull job alerts)

1. In [Google Cloud Console](https://console.cloud.google.com/), create/select
   a project and enable the **Gmail API**.
2. Configure the OAuth consent screen as "External" + "Testing", and add
   your own Gmail address as a test user (avoids needing Google's app
   review for personal use).
3. Create an **OAuth client ID** (type: Web application) with authorized
   redirect URI `http://localhost:8000/api/gmail/oauth/callback`.
4. Put the client ID/secret into `.env`:
   ```bash
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```
5. Restart the backend (`docker compose restart backend` or re-run
   `uvicorn` if running natively) so it picks up the new env vars.
6. Get the consent URL and open it in a browser:
   ```bash
   curl http://localhost:8000/api/gmail/oauth/authorize
   ```
7. After granting access, confirm the account connected (tokens are never
   shown in any response):
   ```bash
   curl http://localhost:8000/api/gmail/accounts
   ```
8. Trigger a sync and see what was found:
   ```bash
   curl -X POST http://localhost:8000/api/gmail/sync
   curl http://localhost:8000/api/gmail/emails
   ```

Ongoing syncs also run automatically via Celery Beat every
`JOB_ALERT_POLL_INTERVAL` minutes once `celery_worker`/`celery_beat` are up
(they start automatically with `docker compose up`).

---

## Project layout

```
job-automation/
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI entrypoint
│   │   ├── api/routes/                   # HTTP routes (health, gmail, ...)
│   │   ├── config/settings.py            # env-driven config
│   │   ├── database/                     # SQLAlchemy engine/session/base
│   │   ├── security/token_encryption.py  # Fernet encryption for OAuth tokens
│   │   ├── gmail/                        # OAuth, client, normalizer, ingestion service
│   │   ├── job_alerts/
│   │   │   ├── contracts/                # JobPlatformParser protocol
│   │   │   ├── dto/                      # NormalizedJob
│   │   │   ├── parsers/{linkedin,indeed,wellfound,generic}/
│   │   │   ├── extraction/               # date extractor, URL extractor, redirect resolver
│   │   │   └── classification/           # RuleBasedClassifier
│   │   ├── jobs/
│   │   │   ├── models/                   # Job, JobCategory, JobPlatform, JobEmail, ProcessingEvent
│   │   │   ├── fingerprinting/           # JobFingerprintService
│   │   │   ├── services/                 # JobProcessingService
│   │   │   └── export/                   # (Phase 6 — not yet implemented)
│   │   ├── tasks/                        # Celery app + scheduled sync task
│   │   ├── schemas/                      # Pydantic request/response models
│   │   └── repositories/                 # DB access layer
│   ├── alembic/versions/                 # 2 migrations: Phase 1, Phase 2-5
│   └── tests/{unit,integration,fixtures}/  # 49 tests
├── frontend/
│   └── src/{components,views,stores,router,services}/
├── docker-compose.yml
└── .env.example
```

Adding a new job platform means adding a parser under
`app/job_alerts/parsers/<platform>/` and registering it in
`ParserRegistry` — it never requires touching Gmail ingestion,
classification, deduplication, or (once built) CSV export.

---

## Verification gate (what's been confirmed working)

```bash
cd backend && source .venv/bin/activate
pytest              # 49 passed
ruff check .         # clean
black --check .      # clean
mypy app             # clean
alembic upgrade head # both migrations apply cleanly
alembic downgrade base  # both migrations reverse cleanly
```

```bash
cd frontend
npm run build        # builds cleanly
```

Manually confirmed:

- `GET /api/health` → `{"status": "ok"}`
- `GET /api/health/db` → `{"status": "ok", "database": "reachable"}`
- Migrations seed LinkedIn/Indeed/Wellfound platforms and 9 job categories
  with keywords
- A test proves the same job fingerprinted from two different emails is
  persisted exactly once, with a `ProcessingEvent` recording the duplicate
- `job_posted_at` is never fabricated — it's `NULL` when the email gives no
  reliable posting-date signal, and is never silently set to `received_at`
