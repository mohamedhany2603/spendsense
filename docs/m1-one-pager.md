# M1 — The one-pager

## The problem (3 sentences)
People who track their spending by hand lose the habit within a couple of weeks because every purchase
has to be typed in, read, and silently categorized into a spreadsheet. The categorization step is the slow,
brainless part — the same brands appear month after month but still get classified by eye. Nobody needs a
charting suite; they need the boring data-entry work to disappear.

## Who has this problem
Anyone who uses a bank statement or a CSV export to understand where their money went, but gives up on
budgeting because manual categorization takes too long.

## The 10x claim
Categorizing a month of transactions with a spreadsheet tool took me about 20 minutes by hand; with
SpendSense the same month is categorized in roughly 30 seconds — one upload or a few adds, and the
LLM does the rest.

## The 5+ concepts from Section 2 (all 7, no swaps)
| # | Concept | Where it lives |
|---|---------|----------------|
| 1 | API endpoints | FastAPI REST API with Pydantic validation and correct status codes |
| 2 | Database | SQLite + SQLAlchemy — data survives restarts |
| 3 | Authentication | JWT login; protected routes verified in the tests |
| 4 | Background jobs / cron | APScheduler: auto-categorize pending transactions + generate monthly PDF reports on a schedule |
| 5 | Reporting — PDF | Monthly report generated as a PDF (ReportLab) and downloadable via an endpoint |
| 6 | Caching logic | LLM categorization results are cached + monthly analytics are cached with a TTL |
| 7 | LLM integration | One narrow job (merchant → category) behind an endpoint, with validation and a cost log |

Swaps used: **none** (all 7 core concepts fit — 0 of the 2 allowed swaps).

## Non-goal (explicitly NOT built)
This project is **not** a bank. There is no real money handling, no external bank/Plaid/Open-Banking
integration, no multi-user org/teams, and no mobile app. Transaction data is the user's own or seeded
demo data only.

## Scope guard
Core feature list stays under 5: (1) add transactions, (2) auto-categorize with LLM + cache, (3) view
monthly analytics, (4) generate monthly PDF report, (5) auth-protect everything. Anything shiny that
appears mid-build goes under "Future ideas" in the README.