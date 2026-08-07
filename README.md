# EARN: Eliciting Actionable Recommendation Feedback

Web platform for the EARN study: participants read a personalized news
newsletter and write open-ended feedback on how they'd like it improved,
under one of three elicitation conditions. Researchers score each response
with a five-dimension actionability rubric and export the data for analysis.

It implements the study described in the proposal "EARN: Eliciting
Actionable Recommendation Feedback from Users for News Personalization."
It only collects and measures feedback — it doesn't apply that feedback to
change future newsletters (that's future work).

## What it does

Participant flow, no account needed, just a private link:

1. Consent — short statement, reminder not to include sensitive info.
2. Read — one fixed-format newsletter (5 sections x 3 articles each).
3. Feedback — depends on condition, see below.
4. Survey — four post-task Likert items on effort and feedback quality.
5. Done — a completion code, works as a Prolific completion code.

Three conditions, randomly assigned and balanced across participants:

| # | Condition | Participant experience |
|---|-----------|------------------------|
| 1 | Just Ask | The prompt, no guidance. |
| 2 | Examples + Instructions | Prompt plus a neutral instruction, guidance questions, and one example. |
| 3 | Interactive Feedback Assistant | Short back-and-forth with an assistant to clarify the feedback. Participant reviews and submits the final version — the assistant never rewrites it for them. |

Condition 3 talks to a self-hosted, OpenAI-compatible local LLM (default
`openai/gpt-oss-120b`). No external provider and no fallback: if the local
endpoint is down, the API returns `503` and the participant can still
submit what they already wrote.

Researcher dashboard (`/researcher`):

- Enrollment overview and balance across condition x newsletter.
- Blind rating queue — five 0/1/2 rubric dimensions plus a target-level
  code. Raters never see the condition or anyone else's score.
- Rater accounts: separate login per rater, one score per response.
- CSV export with feedback, the condition-3 transcript, survey items, and
  rating means.

Statistical analysis isn't part of the app. That's done separately in
R/Python from the CSV export.

## Tech stack

Next.js (App Router) + React + TypeScript on the frontend, Django + DRF on
the backend, PostgreSQL, JWT auth. Three Docker services: db, backend, web.

## Project layout

```
earn/
├── backend/                 # Django + DRF
│   ├── apps/
│   │   ├── core/            # health, pagination, permissions
│   │   ├── users/           # JWT auth, researcher + rater accounts
│   │   └── study/           # newsletters, participants, assistant, rubric, export
│   ├── project_backend/settings/{base,dev,prod}.py
│   ├── system_prompt.txt    # live Condition-3 assistant prompt
│   ├── tests/               # pytest
│   └── Dockerfile
├── web/                     # Next.js
│   └── src/{app,components,lib}
├── documentation/           # codebase documentation (Bangla)
├── IRB/                     # IRB protocol documents + project proposal
├── docker-compose.yml
└── .env.example
```

---

## Quick start

Requires Docker + Docker Compose, plus a self-hosted OpenAI-compatible LLM
reachable at `LOCAL_LLM_BASE_URL` if you want Condition 3 to work.

```bash
./run.sh up         # build + start everything (web, backend, db)
```

First run creates `.env`, builds the images, migrates, seeds 3 newsletters
plus a researcher account, and waits for the backend to be healthy.

- Participant site: <http://localhost:3000>
- Researcher dashboard: <http://localhost:3000/researcher/login>
- Backend API + docs: <http://localhost:8001/api/docs/>
- Researcher login: `RESEARCHER_USERNAME` / `RESEARCHER_PASSWORD` in `.env`.

Change `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and `RESEARCHER_PASSWORD`
before deploying anywhere real.

### `./run.sh` commands

| Command | What it does |
|---------|--------------|
| `up` | Build (if needed) and start everything in the background |
| `down` | Stop and remove containers, keeps the database |
| `restart` | Restart the whole stack |
| `stop` / `start` | Pause / resume without removing containers |
| `rebuild` | Rebuild images from scratch and start |
| `reset` | **Wipes** the database volume and starts fresh (re-seeds) |
| `logs [svc]` | Follow logs, optionally `backend` / `web` / `db` |
| `ps` | Show container status |
| `seed` / `migrate` | Re-seed / migrate |
| `superuser` | Create a Django superuser |
| `manage <args>` | Run any `manage.py` command in the backend |
| `shell` | Shell into the backend container |

Source is copied into the images, no volume mount. After changing backend
or frontend code (or `system_prompt.txt`) you need to rebuild:
`docker compose up -d --build backend` (or `web`). Restarting alone still
runs the old code.

### Ports

Defaults: web `3000`, backend `8001`, loopback-only Postgres `5436`. The
backend uses host networking so it can reach a local LLM at
`127.0.0.1:8123`. Change ports in `.env` (`WEB_PORT`, `BACKEND_PORT`,
`DB_PORT`, keep `NEXT_PUBLIC_API_BASE_URL` matching `BACKEND_PORT`), then
`./run.sh rebuild`.

To reach it over SSH, forward both ports since the browser calls the API
directly:

```bash
ssh -N -L 3000:127.0.0.1:3000 -L 8001:127.0.0.1:8001 user@host
```

---

## Data model

Five models:

| Model | Purpose |
|-------|---------|
| `Newsletter` | Fixed 5x3 stimulus, sections/articles stored as JSON |
| `Participant` | One session: condition, newsletter, status, study phase. Identified by an unguessable `public_id` (UUID) that doubles as the completion code |
| `FeedbackResponse` | 1:1 with participant — `initial_text`, `final_text`, the Condition-3 `chat_log`, and the consolidated `final_draft` |
| `SurveyResponse` | 1:1 with participant, four 1-5 items |
| `ActionabilityRating` | 1:N per response, five 0-2 rubric dimensions plus target level, one row per (response, rater) |

`ActionabilityRating.total` is computed, not stored. Newsletters can't be
deleted while a participant references them. Deleting a rater account
nulls out `rater` on their ratings but keeps the ratings themselves.

## Collecting data with participants

Send each participant to the site root; they get a fresh randomized
assignment:

```
https://your-host/?source=prolific&ref=PROLIFIC_PID
```

- `source` → `recruitment_source` (`direct` | `movielens` | `prolific` | `other`)
- `ref` → `external_ref`, e.g. the Prolific participant id
- The completion code shown at the end is the participant's `public_id`

Assignment is balanced: each new participant fills the least-populated
(condition x newsletter) cell, so the cells stay even as enrollment grows.

### Study phases

`STUDY_PHASE` defaults to `pilot`. URLs like `?condition=3` are stored as
`preview` so demo sessions don't mix into real data. Set
`STUDY_PHASE=main` in `.env` and restart before real recruitment. Balance
is calculated per phase.

### Human raters

The primary researcher account is a study manager. From
`/researcher/raters` they can create, deactivate, and reset credentials
for any number of raters — separate username per person, never share an
account, since every score keeps that rater's identity attached.

Raters sign in at `/researcher/login` and go straight to the blind rating
queue. They can't open the overview, exports, or conversation history —
the queue only shows the final feedback text.

---

## Tests, linting, production build

```bash
# Backend (tests are excluded from the production image, so mount the source)
docker compose run --rm --no-deps -v "$(pwd)/backend:/app" backend \
  sh -c "pip install -q pytest pytest-django && python -m pytest tests/ -q"

# Frontend
cd web
npm run test                   # Vitest
npm run lint                   # ESLint
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
| Current researcher/rater | `GET /api/auth/me/` |
| Create/list human raters | `GET/POST /api/auth/raters/` |
| Update/deactivate/reset rater | `PATCH /api/auth/raters/{id}/` |
| Overview | `GET /api/research/overview/` |
| Responses | `GET /api/research/responses/?condition=&unrated=1` |
| Create rating | `POST /api/research/responses/{id}/ratings/` |
| CSV export | `GET /api/research/export.csv` |

Condition-3 endpoints return `503` when the local model is unreachable.

---

## Environment variables

See `.env.example` (root, for compose), `backend/.env.example`, and
`web/.env.example`. The ones worth knowing about:

| Variable | Where | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | backend | PostgreSQL DSN, required |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | compose | Database credentials |
| `LOCAL_LLM_BASE_URL` | backend | Self-hosted OpenAI-compatible `/v1` base URL |
| `LOCAL_LLM_MODEL` | backend | Defaults to `openai/gpt-oss-120b` |
| `LOCAL_LLM_API_KEY` | backend | Optional local endpoint bearer token |
| `STUDY_PHASE` | backend | `pilot` by default, set to `main` before real recruitment |
| `STUDY_ENABLED_CONDITIONS` | backend | e.g. `1,2` to run without Condition 3 |
| `RESEARCHER_USERNAME` / `RESEARCHER_PASSWORD` | backend | Seeded dashboard login |
| `NEXT_PUBLIC_API_BASE_URL` | web | Backend URL the browser calls, baked in at build time |

## Notes

The three newsletters are rendered in the POPROX style (teal masthead,
dark-blue section bars, thumbnail + label + serif headline + summary),
matching <https://github.com/Mahamudul42/poprox_newsletter>. Each is the
fixed 5x3 format, populated with real Associated Press articles from that
template; the three editions lean toward different topics (world,
politics, tech/sports) so feedback doesn't cluster on one subject. Data
lives in `backend/apps/study/seed_data/newsletters.json`.

Feedback is written on the same page as the newsletter, right underneath
it — same as POPROX's own end-of-newsletter feedback block. No production
newsletter service is required; the study is self-contained.
