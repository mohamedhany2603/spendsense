# SpendSense — LLM-powered expense tracker

**The boring part of budgeting, done in seconds.** Instead of reading and typing each purchase into a
spreadsheet, you drop transactions in and SpendSense categorizes them automatically — with an LLM when an
API key is configured, otherwise with a deterministic rule-based classifier that makes the whole system run
on a $0 stack with no keys at all.

**10x claim:** categorizing a month of transactions from a statement took ~20 minutes by hand; with
SpendSense the same month is done in ~30 seconds.

This is the **"Your 10x Solution" capstone** for the FlyRank Internship — Backend Track. See
`My 10x Solution - Your Name and Surname.md` for the submission overview document.

---

## Concepts implemented (Section 2 of the brief)

**All 7 core concepts — 0 swaps.**

| # | Concept | Where it lives in the code |
|---|---------|---------------------------|
| 1 | API endpoints | `app/routers/*` — FastAPI REST API, correct status codes, Pydantic validation |
| 2 | Database | `app/models.py`, `app/database.py` — SQLAlchemy + SQLite, data survives restarts |
| 3 | Authentication | `app/routers/auth.py`, `app/security.py`, `app/deps.py` — JWT login, protected routes |
| 4 | Background / cron jobs | `app/services/scheduler.py` — APScheduler: auto-categorize (interval) + monthly PDF report (cron) |
| 5 | Reporting — PDF | `app/services/reports.py`, `app/routers/reports.py` — ReportLab monthly report + download endpoint |
| 6 | Caching logic | `app/services/cache.py` — TTL cache for monthly analytics + DB-backed classifier cache for LLM results |
| 7 | LLM integration | `app/services/categorizer.py`, `app/routers/llm.py` — one narrow AI job (merchant → category) with validation and a cost log |

> Swap rule: no swaps used — all 7 concepts from the first table fit the solution.

## Project layout

```
app/
  main.py            FastAPI app + lifespan (schema creation, category seed, scheduler start)
  config.py          typed settings from environment variables (.env)
  database.py        SQLAlchemy engine / session
  models.py          User, Category, Transaction, ClassifierCache, LlmCostLog, Report
  schemas.py         Pydantic request/response models
  security.py        bcrypt hashing + JWT create/decode
  deps.py            DB session + current-user dependency (protects routes)
  routers/           auth, transactions, analytics, llm, reports, health
  services/
    categorizer.py   LLM integration + rule fallback + result caching + cost logging
    cache.py         TTL analytics cache + durable classifier cache
    reports.py       PDF generation (ReportLab)
    scheduler.py     APScheduler background/cron jobs
seed.py              demo user + ~3 months of data (30 categorized, 3 pending)
tests/               pytest suite (40 tests) — run with `pytest`
docs/m1-one-pager.md the M1 one-pager (problem, user, claim, concepts, non-goal)
```

## Requirements

- **Python 3.12+** installed.
- Optional: an **OpenRouter API key** (`OPENROUTER_API_KEY`) for a real LLM. Without it the app runs
  fully with a rule-based classifier and still logs estimated costs.

## Run it on a clean machine

Two commands:

```bash
# 1) Install (do this once)
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 2) Run the API
python run.py                   # -> http://127.0.0.1:8000
```

> If you create no `.env` file, safe defaults apply. To configure your own values, copy `.env.example`
> to `.env` and edit. **Never commit `.env`** — it is in `.gitignore`.
>
> Note for OneDrive-folder copies (this machine): creating a `.venv` inside the synced folder can fail
> with a `WinError 2`. Create the virtual environment outside the folder (e.g. in the temp/system dir)
> and activate it, or just install with `python -m pip install -r requirements.txt`.

Interactive API docs (Swagger UI): <http://127.0.0.1:8000/docs>

## Seed demo data

```bash
python seed.py
```

Creates user **`demo@example.com` / `demo1234`** with ~30 categorized transactions across the last 3
calendar months plus 3 fresh uncategorized ones, so you can watch the background job work.

## 5-minute demo path

1. `python run.py` — app starts, schema is created, the scheduler registers two jobs.
2. Open <http://127.0.0.1:8000/docs>.
3. **POST `/api/auth/login`** → `{"email": "demo@example.com", "password": "demo1234"}` → copy the token.
4. Click **Authorize**, paste the token, and call **GET `/api/transactions`** (_see the categorized data_).
5. Call **GET `/api/transactions?status=pending`** — the 3 seeded pending rows. Wait for the scheduler's
   auto-categorize job (every 5 min) or restart and re-seed, and they become `categorized`.
6. Call **POST `/api/llm/categorize`** with a new merchant (e.g. `{"merchant":"Koala Coffee House"}`) —
   you get a category, source `rule` (or `llm` with a key) and a logged cost. Call it again → source
   `cache`, cost `0`.
7. Call **GET `/api/llm/costs`** — you see the cost log with token usage per categorization.
8. Call **GET `/api/analytics/monthly?month=YYYY-MM`** (previous month) — spend by category. Call it twice:
   the second response has `"cached": true`.
9. Call **POST `/api/reports/generate`** with `{"month":"YYYY-MM"}`, then
   **GET `/api/reports/{id}/download`** — a PDF summary downloads.

## API surface

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Get JWT |
| GET | `/api/auth/me` | JWT | Current user |
| POST | `/api/transactions` | JWT | Add transaction (auto-categorized) |
| POST | `/api/transactions/bulk` | JWT | Add up to 1000 at once |
| GET | `/api/transactions` | JWT | List, filter by `status`/`category_id`, paginate |
| GET/PATCH/DELETE | `/api/transactions/{id}` | JWT | Read, recategorize, delete |
| GET | `/api/analytics/monthly?month=YYYY-MM` | JWT | Cached spending rollup |
| POST | `/api/llm/categorize` | JWT | Narrow AI job: merchant → category |
| GET | `/api/llm/costs` | JWT | LLM cost log (calls, tokens, estimated $) |
| POST | `/api/reports/generate` | JWT | Create monthly PDF report |
| GET | `/api/reports` | JWT | List reports |
| GET | `/api/reports/{id}/download` | JWT | Download the PDF |
| GET | `/health`, `/health/me` | — / JWT | Liveness + scheduler status |

## Tests

```bash
pytest        # 40 tests: auth, validation, caching, LLM cost log, PDF reports, cross-user isolation
```

## How the LLM integration works (and stays $0)

- With `OPENROUTER_API_KEY` set, `app/services/categorizer.py` asks a real model
  (`openai/gpt-4o-mini` by default) to return one category from the allowed list. The reply is parsed and
  **validated strictly** — an unknown category is rejected.
- Without a key, a deterministic keyword classifier runs instead, so nothing is blocked and nothing costs money.
- Every call — real or fallback — is recorded in the `LlmCostLog` table with prompt/completion tokens and an
  estimated US$ cost (priced at public model rates).
- Results are cached per normalized merchant in `ClassifierCache`, so repeat descriptions never hit the LLM again.

## Background / cron jobs (APScheduler)

| Job | Schedule | What it does |
|-----|----------|--------------|
| `auto_categorize` | every `AUTO_CATEGORIZE_INTERVAL_MINUTES` (default 5) | categorizes up to 50 pending transactions |
| `monthly_report` | 1st of each month at `REPORT_CRON_HOUR:REPORT_CRON_MINUTE` | generates last month's PDF for every user |

## Environment variables (see `.env.example`)

`SECRET_KEY`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `CACHE_TTL_SECONDS`,
`ENABLE_SCHEDULER`, `AUTO_CATEGORIZE_INTERVAL_MINUTES`, `REPORT_CRON_HOUR`, `REPORT_CRON_MINUTE`.

## Non-goals (Section 7 of the brief)

No real banking/OAuth bank feeds, no real payments, no multi-user organizations, no mobile app.
Single-user-friendly from the start, seeded with demo data only. The **10x** is about the categorization
work disappearing — not about becoming a bank.

## Future ideas (captured during the build, deliberately NOT built)

- CSV/OFX upload endpoint with an idempotent import pipeline (web-scrape/parse candidate).
- Email delivery of the monthly PDF (SMTP on a free tier).
- Dockerfile + `docker compose up` packaging.
- Free-tier deployment (PythonAnywhere/Railway) for a live URL.
- RAG over past transactions: "where did I overspend?" with citations.