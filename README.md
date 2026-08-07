# EARN — Eliciting Actionable Recommendation Feedback

A full-stack web platform for running the **EARN** between-subjects online
experiment: participants read a realistic personalized news newsletter and write
open-ended feedback about how they'd like it improved, under one of three
elicitation conditions. Researchers then score each response with a
five-dimension actionability rubric and export the data for analysis.

> This implements the study described in the project proposal
> *“EARN: Eliciting Actionable Recommendation Feedback from Users for News
> Personalization.”* It collects and measures feedback; it does **not** apply
> feedback to change future newsletters (that is future work).

## What it does

**Participant flow** (no account needed — a private link per participant):

1. **Consent** — short statement; reminder not to include sensitive info.
2. **Read** — one fixed-format newsletter (5 sections × 3 articles).
3. **Feedback** — condition-specific (see below).
4. **Survey** — four post-task Likert items about effort and feedback quality.
5. **Done** — completion code (usable as a Prolific completion code).

**Three elicitation conditions** (randomly + balance-assigned per participant):

| # | Condition | Participant experience |
|---|-----------|------------------------|
| 1 | **Just Ask** | The prompt only — no guidance. |
| 2 | **Examples + Instructions** | Prompt + a neutral instruction, guidance questions, and one example. |
| 3 | **Interactive Feedback Assistant** | Participant writes feedback and has a short clarification conversation with the assistant. The participant reviews and submits the final version; the assistant never rewrites their feedback for them. |

The assistant uses the self-hosted **OpenAI-compatible local LLM** (default
`openai/gpt-oss-120b`). It never falls back to an external provider; if the
local endpoint is unavailable, the built-in **deterministic rule-based**
assistant keeps the participant flow usable without exporting participant data.

**Researcher dashboard** (`/researcher`):

- Enrollment overview + balance across (condition × newsletter).
- A rating queue applying the **0–10 actionability rubric** (five 0/1/2
  dimensions: target specificity, direction/operation, collection allocation,
  context/persistence, system feasibility) plus a target-level code.
- One-click **CSV export** with feedback, survey items, and rating means.

## Tech stack

- **Frontend:** Next.js (App Router) · React · TypeScript · Tailwind CSS ·
  lucide-react · Vitest.
- **Backend:** Django 5 · Django REST Framework · JWT (simplejwt) ·
  drf-spectacular (OpenAPI).
- **Database:** PostgreSQL 16.
- **Containers:** Dockerfiles + `docker-compose` (PostgreSQL, backend, web).

## Project layout

```
earn/
├── backend/                 # Django + DRF
│   ├── apps/
│   │   ├── core/            # health, pagination, permissions
│   │   ├── users/           # JWT auth, researcher account
│   │   └── study/           # newsletters, participants, assistant, rubric, export
│   ├── project_backend/settings/{base,dev,prod}.py
│   ├── tests/               # pytest
│   └── Dockerfile
├── web/                     # Next.js
│   └── src/{app,components,lib}
├── IRB/                     # IRB protocol documents
├── Eliciting_Actionable_Recommendation_Feedback_Proposal (11).docx
├── docker-compose.yml
└── .env.example
```

---

## Quick start — Docker (recommended)

Requires Docker + Docker Compose. One script runs everything:

```bash
./run.sh up         # build + start the whole stack (web, backend, db)
```

That's it. The script creates `.env` on first run, builds the images, migrates,
seeds (3 newsletters + a researcher account), and waits until the backend is
healthy before printing the URLs.

- Participant site: <http://localhost:3000>
- Researcher dashboard: <http://localhost:3000/researcher/login>
- Backend API + docs: <http://localhost:8001/api/docs/>
- Researcher login: values configured by `RESEARCHER_USERNAME` and
  `RESEARCHER_PASSWORD` in `.env`.

For a new deployment, change `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and
`RESEARCHER_PASSWORD` before starting the stack.

### Manage the stack with `./run.sh`

| Command | What it does |
|---------|--------------|
| `./run.sh up` | Build (if needed) and start everything in the background |
| `./run.sh down` | Stop and remove containers (keeps the database) |
| `./run.sh restart` | Restart the whole stack |
| `./run.sh stop` / `start` | Pause / resume without removing containers |
| `./run.sh rebuild` | Rebuild images from scratch and start |
| `./run.sh reset` | **Wipe** the database volume and start fresh (re-seeds) |
| `./run.sh logs [svc]` | Follow logs (optionally `backend` / `web` / `db`) |
| `./run.sh ps` | Show container status |
| `./run.sh seed` / `migrate` | Re-seed / migrate |
| `./run.sh superuser` | Create a Django superuser |
| `./run.sh manage <args>` | Run any `manage.py` command in the backend |
| `./run.sh shell` | Shell into the backend container |
| `./run.sh help` | Full usage |

### Ports

Defaults are chosen to avoid clashing with other services: **web `3000`**,
**backend `8001`**, and loopback-only Postgres `5436`.
The Linux backend container uses host networking so it can reach the local LLM
at `127.0.0.1:8123`. Change ports in `.env` (`WEB_PORT`, `BACKEND_PORT`,
`DB_PORT`, and keep `NEXT_PUBLIC_API_BASE_URL` matching `BACKEND_PORT`), then
run `./run.sh rebuild`.

### Access from Windows over SSH

The frontend calls the API from the browser, so forward both the web and API
ports. For this server's current `.env` (`WEB_PORT=3002`,
`BACKEND_PORT=8001`), run the following in Windows PowerShell and leave the
terminal open:

```powershell
ssh -N -o ExitOnForwardFailure=yes `
  -L 3002:127.0.0.1:3002 `
  -L 8001:127.0.0.1:8001 `
  hasan181@cs-u-jamjar.cs.umn.edu
```

Then open <http://localhost:3002/?condition=3> to force the Condition-3 flow.
The researcher dashboard is available at
<http://localhost:3002/researcher/login>. If the SSH connection already exists,
open a second PowerShell window for this tunnel command.

---

## Quick start — local, no Docker

This path requires a running PostgreSQL instance. Create the `earn` database
and user, then set `DATABASE_URL` to its DSN. The example below uses the same
loopback port and credentials as `.env.example`:

### Backend (terminal 1)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
export DATABASE_URL=postgres://earn:change-me-db-password@127.0.0.1:5436/earn
python manage.py migrate
python manage.py seed_study           # newsletters + researcher account
python manage.py runserver 0.0.0.0:8000
```

### Frontend (terminal 2)

```bash
cd web
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev
```

Open <http://localhost:3000>.

---

## The Interactive Feedback Assistant (Condition 3)

- **Local model:** set `LOCAL_LLM_BASE_URL` and optionally `LOCAL_LLM_MODEL`
  (default `openai/gpt-oss-120b`). `LOCAL_LLM_API_KEY` is optional because the
  current endpoint does not require authentication.
- **When the local endpoint fails:** a deterministic fallback asks a targeted
  clarifying question. `assistant_used_llm` records which path produced each
  turn. There is deliberately no external-provider fallback.

---

## Collecting data with participants

Send each participant to the site root; they get a fresh randomized assignment:

```
https://your-host/?source=prolific&ref=PROLIFIC_PID
```

- `source` → recorded as `recruitment_source` (`direct` | `movielens` |
  `prolific` | `other`).
- `ref` → recorded as `external_ref` (e.g. the Prolific participant id).
- The completion code shown at the end is the participant’s `public_id`.

Assignment is **balanced**: each new participant fills the least-populated
(condition × newsletter) cell, so the design stays even as enrollment grows
toward the target (~60 per condition).

---

## Tests, linting, production build

```bash
# Backend
cd backend && source .venv/bin/activate
pytest                         # auth, assistant, balanced assignment, full flow, permissions

# Frontend
cd web
npm run test                   # Vitest
npm run lint                   # ESLint (next/core-web-vitals)
npm run build                  # production build + type check
```

## API reference

Interactive OpenAPI docs at `/api/docs/` (Swagger) and `/api/redoc/`.

| Area | Endpoint |
|------|----------|
| Health | `GET /api/health/` |
| Start session | `POST /api/session/start/` |
| Get session | `GET /api/session/{public_id}/` |
| Consent | `POST /api/session/{public_id}/consent/` |
| Initial feedback (+assistant) | `POST /api/session/{public_id}/feedback/initial/` |
| Assistant follow-up | `POST /api/session/{public_id}/feedback/chat/` |
| Consolidated final draft | `POST /api/session/{public_id}/feedback/final-draft/` |
| Final feedback | `POST /api/session/{public_id}/feedback/final/` |
| Survey | `POST /api/session/{public_id}/survey/` |
| Researcher login | `POST /api/auth/token/` |
| Overview | `GET /api/research/overview/` |
| Responses | `GET /api/research/responses/?condition=&unrated=1` |
| Create rating | `POST /api/research/responses/{id}/ratings/` |
| CSV export | `GET /api/research/export.csv` |

---

## Environment variables

See `.env.example` (root, for compose), `backend/.env.example`, and
`web/.env.example`. Highlights:

| Variable | Where | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | backend | PostgreSQL DSN (required for local and production use) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | compose | PostgreSQL database credentials |
| `LOCAL_LLM_BASE_URL` | backend | Self-hosted OpenAI-compatible `/v1` base URL |
| `LOCAL_LLM_MODEL` | backend | Defaults to `openai/gpt-oss-120b` |
| `LOCAL_LLM_API_KEY` | backend | Optional local endpoint bearer token |
| `RESEARCHER_USERNAME` / `RESEARCHER_PASSWORD` | backend | Seeded dashboard login |
| `NEXT_PUBLIC_API_BASE_URL` | web | Backend URL the browser calls |

## Implementation notes

- **Stimuli** are three fixed newsletters rendered in the **POPROX newsletter
  style** (teal masthead, dark-blue section bars, thumbnail + topic-label +
  serif headline + summary), matching the reference template at
  <https://github.com/Mahamudul42/poprox_newsletter>. Each has the fixed 5×3
  format (five sections, three articles) and is populated with **real Associated
  Press articles** (headline, summary, image, link) harvested from that template;
  the three editions differ in topical emphasis (world, U.S./politics,
  tech/sports) for feedback diversity. Stimulus data lives in
  `backend/apps/study/seed_data/newsletters.json`.
- **Feedback is on the same page as the newsletter** — the participant reads the
  newsletter and writes feedback directly beneath it (mirroring POPROX's own
  end-of-newsletter feedback block), rather than on a separate screen.
- **No production newsletter service is required** — the study is
  self-contained and uses fixed newsletter stimuli.
- **LLM rubric scoring** is available through the `rate_with_llm` management
  command. Human ratings remain separate through the `is_llm` field.
