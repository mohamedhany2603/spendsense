# My 10x Solution - Mohamed Hany

*FlyRank Internship · Backend Track · Capstone — "Your 10x Solution"*

Repository: https://github.com/mohamedhany2603/spendsense

---

## 1. What is the problem you are solving?

People who want to track their spending usually give up within a couple of weeks, and the reason is almost
never the numbers — it is the data entry. Every purchase has to be read from a bank statement or CSV,
typed in, and quietly categorized into a spreadsheet by eye. That is slow, boring, and easily the most
unpleasant part of budgeting. This project removes exactly that step.

**Who has this problem:** anyone who wants to know where their money went but does not have the patience
to hand-categorize a month of transactions in a spreadsheet.

**The 10x claim:** categorizing a month of transactions from a statement took me about 20 minutes by hand;
with SpendSense the same month is done in roughly 30 seconds — you add transactions, and the AI (or a $0
rule-based fallback) categorizes them automatically.

## 2. How did you implement your solution?

SpendSense is a Python backend built with **FastAPI**. A user registers and logs in (JWT). They add
transactions through a REST API. Each transaction is categorized automatically: the app first checks a
per-merchant cache, then calls a narrow LLM job (OpenRouter, optional key), and otherwise falls back to a
deterministic rule-based classifier so the whole system runs on **$0 with no API key** on a clean machine.
Every AI call — real or fallback — is logged with token usage and estimated cost. Users can view monthly
spending rollups by category and download a generated **PDF monthly report**. A small **APScheduler**
setup runs two jobs off the request path: it auto-categorizes pending transactions every few minutes, and
on the 1st of each month it pre-generates the previous month's PDF for every user.

### The 5+ program concepts (Section 2 of the brief)

All **7 core concepts** are implemented — the solution fits all of them, so **no swaps were needed**:

| Concept | What was implemented | Where it lives |
|---------|----------------------|----------------|
| 1. API endpoints | FastAPI REST API with correct status codes and Pydantic validation (401/404/409/422/204 checks are in the test suite) | `app/routers/*` |
| 2. Database | SQLAlchemy + SQLite — transactions, users, categories, cost log, cache, reports persist across restarts | `app/models.py`, `app/database.py` |
| 3. Authentication | bcrypt password hashing + JWT tokens; protected routes actually reject anonymous callers | `app/security.py`, `app/deps.py`, `app/routers/auth.py` |
| 4. Background / cron jobs | APScheduler: auto-categorize pending transactions (interval) + monthly PDF generation (cron) | `app/services/scheduler.py` |
| 5. Reporting — PDF | Monthly expense report generated with ReportLab and downloadable via an endpoint | `app/services/reports.py`, `app/routers/reports.py` |
| 6. Caching logic | Monthly analytics aggregated once and reused with a TTL (invalidated on writes); merchant→category results cached in the DB | `app/services/cache.py` |
| 7. LLM integration | One narrow AI job behind an endpoint — "merchant string → category" — reply is validated strictly and every call is recorded in a cost log | `app/services/categorizer.py`, `app/routers/llm.py` |

Swaps used: **0 of 2 allowed** (a summary row was retained for the audience: all seven concepts from the
first table; no swap reason is therefore needed).

### Steps to run it

```bash
python -m venv .venv
.venv\Scripts\activate          # or: source .venv/bin/activate
pip install -r requirements.txt
python seed.py                  # demo user demo@example.com / demo1234, ~3 months of data
python run.py                   # API at http://127.0.0.1:8000 — Swagger UI at /docs
```

No API key is required to run everything. To use a real LLM, copy `.env.example` to `.env` and set
`OPENROUTER_API_KEY`.

### Bonus (beyond the required 5)

- **Test suite:** 40 pytest tests (`pytest`) covering the scary cases — cross-user data isolation,
  validation edge cases, cache behaviour, LLM cost logging, PDF report generation.
- **5-minute demo path** documented in the README, verified end-to-end against a live server.
- **Health endpoint** reporting DB and scheduler status (`/health`).

## 3. Explicit non-goals (scope guard)

Real banking integration, real payments, multi-user teams, and a mobile app are outside this project's
scope on purpose. Transaction data is the user's own or seeded demo data only. A small solution that runs
beats a big solution that doesn't.