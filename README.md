# EARN: Eliciting Actionable Recommendation Feedback

Web platform for the EARN study: participants read a personalized news
newsletter and write open-ended feedback on how they'd like it improved,
under one of three elicitation conditions. Researchers score each response
with a five-dimension actionability rubric and export the data for analysis.

It implements the study described in the proposal "EARN: Eliciting
Actionable Recommendation Feedback from Users for News Personalization."
It only collects and measures feedback -- it doesn't apply that feedback to
change future newsletters (that's future work).

## What it does

Participant flow, no account needed, just the study link:

1. Consent -- short statement, reminder not to include sensitive info.
2. Read -- one fixed-format newsletter (5 sections * 3 articles each).
3. Feedback -- depends on condition, see below.
4. Survey -- four post-task Likert items on effort and feedback quality.
5. Done -- a completion code, works as a Movielens/Prolific completion code.

Three conditions, randomly assigned and balanced across participants:

| # | Condition | Participant experience |
|---|-----------|------------------------|
| 1 | Just Ask | The prompt, no guidance. |
| 2 | Examples + Instructions | Prompt plus a neutral instruction, guidance questions, and one example. |
| 3 | Interactive Feedback Assistant | Short back-and-forth with an assistant to clarify the feedback. Participant reviews and submits the final version -- the assistant never rewrites it for them. |

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


## Tech stack

Next.js (App Router) + React + TypeScript on the frontend, Django + DRF on
the backend, PostgreSQL, JWT auth.

The Docker build compiles the frontend to static files and copies them into
the Django image, so one container serves the participant site, the researcher
dashboard and `/api/` on a single port. Two services: `app` and `db`. The
development machine and the experiment VM build and run the same image and
differ only in `.env`.

## Project layout

```
earn/
├── backend/                 # Django + DRF
│   ├── apps/
│   │   ├── core/            # health, pagination, permissions
│   │   ├── users/           # JWT auth, researcher + rater accounts
│   │   └── study/           # newsletters, participants, assistant, rubric, export
│   ├── project_backend/settings.py
│   ├── system_prompt.txt    # live Condition-3 assistant prompt
│   └── tests/               # pytest
├── web/                     # Next.js, compiled to static files at build time
│   └── src/{app,components,lib}
├── Dockerfile               # frontend build -> Django image
├── docker-compose.yml
└── .env.example
```

---

## Quick start

Requires Docker + Docker Compose, plus a self-hosted OpenAI-compatible LLM
reachable at `LOCAL_LLM_BASE_URL` for Condition 3 to work.

```bash
./run.sh up         # build + start everything (app, db)
```

Before the first run, copy `.env.example` to `.env` and set
`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and `RESEARCHER_PASSWORD`. Then the
script builds the images, migrates, seeds 3 newsletters plus a researcher
account, and waits for the backend to be healthy.

Everything is on one port:

- Participant site: <http://localhost:3000>
- Researcher dashboard: <http://localhost:3000/researcher/login>
- API + docs: <http://localhost:3000/api/docs/>
- Researcher login: `RESEARCHER_USERNAME` / `RESEARCHER_PASSWORD` in `.env`.

The three credential variables above are required; the application does not
provide default passwords or a default Django secret key.

### `./run.sh` commands

| Command | What it does |
|---------|--------------|
| `up` | Build (if needed) and start everything in the background |
| `down` | Stop and remove containers, keeps the database |
| `restart` | Restart the whole stack |
| `stop` / `start` | Pause / resume without removing containers |
| `rebuild` | Rebuild images from scratch and start |
| `reset` | **Wipes** the database volume and starts fresh (re-seeds) |
| `logs [svc]` | Follow logs, optionally `app` / `db` |
| `ps` | Show container status |
| `seed` / `migrate` | Re-seed / migrate |
| `superuser` | Create a Django superuser |
| `manage <args>` | Run any `manage.py` command in the app |
| `test` | Run the backend test suite |
| `shell` | Shell into the app container |

Source is compiled into the image, no volume mount, so every change needs a
rebuild — always the same command:

```bash
git pull && ./run.sh up
```

That covers frontend, backend, `system_prompt.txt`, migrations (they run at
container start), dependencies and the compose file. The one thing it does not
cover is a new **required** variable in `.env.example`: `.env` is not in git,
so add it by hand on the target machine. Compose fails loudly if one is
missing rather than starting up wrong. The `pgdata` volume survives rebuilds;
only `./run.sh reset` deletes data.

Rebuilds are mostly cached: a backend-only change takes a few seconds, a
frontend change about half a minute, and a cold `--no-cache` build about five.

### Ports

One application port, `APP_PORT` (default `3000`), plus loopback-only
Postgres on `DB_PORT` (default `5436`) and a local LLM the backend alone
reaches at `127.0.0.1:8123`. Change them in `.env`, then `./run.sh up`.

Apache on the experiment VM is configured around port 3000; do not change
`APP_PORT` there.

One SSH tunnel is enough, because the browser never talks to a second port:

```bash
ssh -N -L 3000:127.0.0.1:3000 user@host
```

### Frontend hot reload (optional)

The normal loop is a rebuild. When iterating on the UI it can be quicker to
run the Next dev server against the container: start the stack, put
`NEXT_PUBLIC_API_BASE_URL=http://localhost:3000` in `web/.env.local`, add
`http://localhost:3001` to `CORS_ALLOWED_ORIGINS` in `.env`, restart the app
and run `cd web && npm run dev -- -p 3001`. Nothing else in the project
depends on this.

---

## Data model

Five models:

| Model | Purpose |
|-------|---------|
| `Newsletter` | Fixed 5*3 stimulus, sections/articles stored as JSON |
| `Participant` | One session: condition, newsletter, status, study phase. Identified by an unguessable `public_id` (UUID) that doubles as the completion code |
| `FeedbackResponse` | 1:1 with participant — `initial_text`, `final_text`, the Condition-3 `chat_log`, and the consolidated `final_draft` |
| `SurveyResponse` | 1:1 with participant, four 1-5 items |
| `ActionabilityRating` | 1:N per response, five 0-2 rubric dimensions plus target level, one row per (response, rater) |


## Collecting data with participants

Send each participant to the site root; they get a fresh randomized
assignment:

```
https://our-host/?source=movielens&ref=PID
```

- `source` > `recruitment_source` (`direct` | `movielens` | `prolific` | `other`)
- `ref` > `external_ref`, e.g. the Prolific participant id
- The completion code shown at the end is the participant's `public_id`

Assignment is balanced: each new participant fills the least-populated
(condition * newsletter) cell, so the cells stay even as enrollment grows.

### Study phases

`STUDY_PHASE` defaults to `pilot`. URLs like `?condition=3` are stored as
`preview` so demo sessions don't mix into real data. Need to set
`STUDY_PHASE=main` in `.env` and restart before real recruitment. Balance
is calculated per phase.

### Human raters

The primary researcher account is a study manager. From
`/researcher/raters` they can create, deactivate, and reset credentials
for any number of raters -- separate username per person, never share an
account, since every score keeps that rater's identity attached.

Raters sign in at `/researcher/login` and go straight to the blind rating
queue. They can't open the overview, exports, or conversation history —
the queue only shows the final feedback text.

---

## Tests, linting, production build

```bash
./run.sh test                  # backend pytest suite

# Frontend
cd web
npm run test                   # Vitest
npm run lint                   # ESLint
npm run build                  # static export + type check, output in web/out
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

See `.env.example`, the single source for both machines. The ones worth
knowing about:

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
| `APP_PORT` | compose | The one public port; 3000 on the experiment VM |
| `DJANGO_ALLOWED_HOSTS` | backend | Must include the hostname the browser uses — Django serves the HTML too |

## Notes

The three newsletters are rendered in the POPROX style,
matching <https://github.com/Mahamudul42/poprox_newsletter>. Each is the
fixed 5*3 format, populated with real Associated Press articles from that
template; the three editions lean toward different topics (world,
politics, tech/sports) so feedback doesn't cluster on one subject. Data
lives in `backend/apps/study/seed_data/newsletters.json`.

Feedback is written on the same page as the newsletter, right underneath
it — same as POPROX's own end-of-newsletter feedback block. 
