# JobPilot — Backend API

Read-only analytics backend for JobPilot, a personal internship search and
application tracker.

It reads your spreadsheet (locally as CSV, or live from Google Sheets in
read-only mode) and exposes stable JSON endpoints for a React + TypeScript
frontend that will be built later.

**Nothing in this backend writes.** There is no code path that appends, updates
or deletes a spreadsheet record, and no endpoint that modifies a CSV.

---

## Table of contents

1. [Architecture](#1-architecture)
2. [Folder structure](#2-folder-structure)
3. [Setup on Windows](#3-setup-on-windows)
4. [Running the server](#4-running-the-server)
5. [Running the tests](#5-running-the-tests)
6. [CSV mode (default)](#6-csv-mode-default)
7. [Google Sheets read-only mode](#7-google-sheets-read-only-mode)
8. [How statuses are categorised](#8-how-statuses-are-categorised)
9. [How matching works](#9-how-matching-works)
10. [API endpoints](#10-api-endpoints)
11. [Frontend readiness](#11-frontend-readiness)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Architecture

```
n8n workflow  ──writes──▶  Google Spreadsheet  ──read-only──┐
  (not built yet)          Applications / Job Openings       │
                          dataset/ CSV exports  ─────────────┤
                                                            ▼
                                                  ┌──────────────────┐
                                                  │  FastAPI backend │
                                                  │  (this folder)   │
                                                  └────────┬─────────┘
                                                           │ JSON
                                                           ▼
                                                  React + TypeScript
                                                  (built later)
```

Data flow, in order:

| Step | Module | What happens |
| --- | --- | --- |
| 1. Settings | `app/config.py` | Environment variables + `backend/.env` are read into an immutable `Settings` object. |
| 2. Load | `app/sheets.py` | Either the local CSVs or the two Google Sheets tabs are read, then normalised into two `pandas` DataFrames. Google Sheets results are cached for a short TTL. |
| 3. Analyse | `app/analytics.py` | Pure functions compute application analytics, job analytics, de-duplication and preference matching. No I/O here. |
| 4. Serve | `app/schemas.py` + `app/main.py` | Pydantic models define the response shapes; FastAPI routes validate input and return JSON. |

Design decisions worth knowing:

- **Single source of truth per request.** Each request reads one consistent
  `Dataset` snapshot (both tabs together), so numbers on one page always agree.
- **Normalisation happens once, at load time.** Column names, missing values and
  dates are cleaned before analytics run, so the analytics code stays simple.
- **Read-only by construction.** The service account is granted only the
  `spreadsheets.readonly` OAuth scope, and the Google Sheets client only ever
  calls `get_all_values()`.

### Data flow details

CSV mode re-reads the files on each request (they are tiny and local).
Google Sheets mode serves a cached snapshot for `SHEETS_CACHE_TTL_SECONDS`
(default 300) so a page load does not burn API quota, and calls
`repository.invalidate_cache()` to force a refresh.

---

## 2. Folder structure

```
JobPilot/
├── dataset/                     # your original CSV exports (untouched)
│   ├── applications.csv
│   └── job_openings.csv
│
└── backend/
    ├── app/
    │   ├── __init__.py          # package docstring
    │   ├── config.py            # environment-driven Settings
    │   ├── sheets.py            # CSV + Google Sheets read-only data sources
    │   ├── analytics.py         # analytics, de-duplication, matching
    │   ├── schemas.py           # Pydantic response models
    │   └── main.py              # FastAPI app, routes, CORS, error handling
    │
    ├── tests/
    │   ├── conftest.py          # fixtures (synthetic + copies of real CSVs)
    │   ├── test_analytics.py    # analytics, dates, dedupe, matching
    │   └── test_api.py          # every HTTP endpoint
    │
    ├── data/                    # working copies used by CSV mode (git-ignored)
    │   ├── applications.csv
    │   └── job_openings.csv
    │
    ├── .env.example             # template — copy to .env, placeholders only
    ├── .gitignore
    ├── pyproject.toml           # pytest + ruff config
    ├── requirements.txt
    └── README.md
```

`dataset/` holds your original exports and is never written to.
`backend/data/` holds the copies the app actually reads, and is git-ignored
because it contains personal notes.

---

## 3. Setup on Windows

Requires **Python 3.10 or newer**. (Developed and tested on 3.10.0; 3.11/3.12
work fine.)

Open PowerShell in the `backend` folder:

```powershell
cd "D:\CSE\projects\job tracker automation\JobPilot\backend"

# 1. Create the virtual environment
python -m venv .venv

# 2. Activate it
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **If `Activate.ps1` fails** with *"running scripts is disabled on this
> system"*, either allow scripts for your user once:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
> …or skip activation and always use the venv's interpreter directly:
> ```powershell
> .\.venv\Scripts\python.exe -m pip install -r requirements.txt
> .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
> ```

Optional: create your local settings file.

```powershell
Copy-Item .env.example .env
```

`backend/.env` is git-ignored. It is optional — with no `.env` at all the app
starts in CSV mode.

---

## 4. Running the server

From the `backend` folder:

```powershell
python -m uvicorn app.main:app --reload
```

Then open:

- API docs (Swagger UI): <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/api/health>

Useful flags:

```powershell
python -m uvicorn app.main:app --reload --port 8080 --host 0.0.0.0
```

---

## 5. Running the tests

```powershell
python -m pytest              # everything
python -m pytest -v           # verbose
python -m pytest tests/test_analytics.py
python -m pytest -k "matching or duplicate"
```

Expected result on a clean checkout: **141 passed**.

Tests never touch `dataset/` or `backend/data/` directly — the "real data"
tests copy the CSVs into a temporary folder first and assert against that copy.
All synthetic fixtures are written to `tmp_path` and contain invented data only.

---

## 6. CSV mode (default)

CSV mode is the default and needs no credentials.

1. Export both sheets to CSV.
2. Put the files in `backend/data/` (or point `DATA_DIR` elsewhere):

```powershell
Copy-Item ..\dataset\applications.csv .\data\applications.csv
Copy-Item ..\dataset\job_openings.csv  .\data\job_openings.csv
```

3. Make sure `.env` (or your shell) contains:

```dotenv
DATA_SOURCE=csv
DATA_DIR=data
```

### How the exported layout is handled

Your real `applications.csv` has a title block and a summary row above the
actual header:

| Row | Content |
| --- | --- |
| 1–3 | Empty, then the title *"Job & Internship Application Tracker"* |
| 4 | Summary stats: `Total Applications 25`, `Active Applications 15`, `Rejected 10` |
| 5–6 | Empty |
| **7** | **The real header** |
| 8+ | Application records |

The loader detects this automatically:

- It scans for the **first row that looks like a header** — at least 3 non-empty
  cells and no cell that is a number or a date. Row 4 fails because `25`, `15`
  and `10` are numbers; row 7 passes.
- The **empty leading column** (the Sheets row-number gutter) is dropped, but
  only when it is both unnamed *and* entirely empty — an unnamed column holding
  real data is kept and renamed `unnamed_<n>` rather than discarded.
- Header names are slugged and mapped to canonical names, so
  `Role/Position` → `role`, `Job ID/Req ID` → `job_id`, `Platform/Portal` → `platform`.
  Unknown columns are kept under their slug, so nothing is thrown away.
- Placeholder cells — `""`, `N/A`, `None`, `-`, `null` — all count as **missing**
  (and are reported in `missing_data_counts`), but never crash a calculation.
- Dates are parsed with `errors="coerce"`: `2026-09-11` becomes a timestamp and
  `not-a-date` becomes a null that is simply excluded from the monthly trend.
- `job_openings.csv` containing **only headers** loads as a valid, empty
  dataset. Nothing is ever invented to fill it.

---

## 7. Google Sheets read-only mode

### 7.1 Create a service account

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and
   create (or pick) a project.
2. Enable the **Google Sheets API**:
   *APIs & Services → Library → search "Google Sheets API" → Enable*.
3. Create a service account:
   *APIs & Services → Credentials → Create credentials → Service account*.
4. Create a JSON key for it and download it. Rename it `credentials.json` and
   put it **outside version control**, e.g. `backend/secrets/credentials.json`.
5. Copy the service account's `client_email` (something like
   `jobpilot@your-project.iam.gserviceaccount.com`).

### 7.2 Share the spreadsheet

1. Open the spreadsheet in Google Sheets.
2. **Share** → add the service account e-mail as an **Editor or Viewer**.

   *Viewer is enough* — the backend only reads. If your Google Workspace
   domain restricts external sharing, ask an admin to allow the service account.

3. Copy the **spreadsheet ID** out of the URL:
   `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`

### 7.3 Configure `.env`

```dotenv
DATA_SOURCE=google_sheets

GOOGLE_SHEETS_SPREADSHEET_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789
GOOGLE_APPLICATION_CREDENTIALS=secrets/credentials.json

GOOGLE_SHEETS_APPLICATIONS_TAB=Applications
GOOGLE_SHEETS_JOBS_TAB=Job Openings

SHEETS_CACHE_TTL_SECONDS=300
```

Relative paths are resolved from the `backend/` folder, so
`secrets/credentials.json` and an absolute `C:\Users\...\credentials.json` both
work.

> **Is your Applications tab actually called `Sheet1`?**
> Set it and nothing else — the backend never renames a tab:
> ```dotenv
> GOOGLE_SHEETS_APPLICATIONS_TAB=Sheet1
> ```
> Check the real name via `GET /api/health`, which echoes the tab names it is
> configured to use, or in `GET /api/meta`.

### 7.4 What Sheets mode guarantees

- **Read-only.** `gspread` authorises with only the `spreadsheets.readonly`
  scope and the workbook is opened with `Client.open_by_key(spreadsheet_id)` —
  `gspread` has no `readonly` argument, so the scope *is* the enforcement. The
  only call made is `get_all_values()`.
- **No daily CSV export.** Data is fetched live on every request, or served
  from a cache that expires after `SHEETS_CACHE_TTL_SECONDS` (`0` disables the
  cache entirely).
- **Empty tabs are fine.** A missing or empty `Job Openings` tab yields zero
  listings, not an error.
- **Graceful failures.** Auth, permission, quota and not-found problems become
  typed errors surfaced as `503` responses with a safe message. `GET /api/health`
  returns `status: "degraded"` with the reason instead of failing outright.
- **Credentials stay on the backend.** No credential, key path or spreadsheet
  ID is ever included in an API response, and nothing is sent to the frontend.

### 7.5 Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_SOURCE` | `csv` | `csv` or `google_sheets`. |
| `DATA_DIR` | `data` | CSV folder (relative paths resolve from `backend/`). |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | – | Spreadsheet ID from the URL. |
| `GOOGLE_APPLICATION_CREDENTIALS` | – | Path to the service-account JSON key. |
| `GOOGLE_SHEETS_APPLICATIONS_TAB` | `Applications` | Applications tab name. Set to `Sheet1` if needed. |
| `GOOGLE_SHEETS_JOBS_TAB` | `Job Openings` | Job openings tab name. |
| `SHEETS_CACHE_TTL_SECONDS` | `300` | Cache lifetime; `0` disables caching. |
| `SHEETS_READ_RETRY_ATTEMPTS` | `2` | Retries for transient Sheets failures. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins. |
| `DEFAULT_PAGE_SIZE` | `50` | Default `page_size`. |
| `MAX_PAGE_SIZE` | `200` | Upper bound for `page_size`. |
| `ENVIRONMENT` | `development` | Reported by `/api/health`. |

### 7.6 Current status of this integration

**Google Sheets mode is implemented but has not been verified against your real
spreadsheet**, because no service-account credential or spreadsheet ID is
configured in this workspace. What *is* verified by the test suite:

- the settings are read and surfaced correctly;
- an unconfigured or missing-credentials setup degrades cleanly instead of
  crashing;
- the tab names are configurable (including `Sheet1`);
- the cache honours its TTL and can be invalidated;
- the Google client is only ever opened read-only.

To finish: add the two credential variables to `backend/.env`, set the real
Applications tab name, restart the server, and confirm
`GET /api/health` reports `status: "ok"` with a non-zero `applications_rows`.

---

## 8. How statuses are categorised

Raw statuses are preserved exactly as written in the sheet. For analytics, each
one is mapped onto one of five **mutually exclusive** categories using an
ordered keyword table (`app/analytics.py` → `STATUS_RULES`, first match wins):

| Order | Category | Keywords |
| --- | --- | --- |
| 1 | `offer` | offer, offer letter, hired, selected, accepted, onboarded |
| 2 | `rejected` | reject, rejected, not shortlisted, not selected, declined, unsuccessful, did not select, closed, no longer under consideration, not moving forward |
| 3 | `interview` | interview, assessment, oa, aptitude, test, scheduled, shortlisted for, round(s), group discussion, gd, hr screen, hiring |
| 4 | `pending` | submitted, applied, awaiting, in progress, in process, pending, no change, drive, registered, invited, under review, screening |

Anything that matches nothing becomes `other`. **An unknown status is never
guessed into `pending` or `rejected`.**

Order matters and is deliberate: `"Assessment Completed & Submitted"` matches
rule 3 (`assessment`) before it ever reaches rule 4 (`submitted`), so it counts
as interview-stage rather than pending.

How your current statuses resolve:

| Status in the sheet | Count | Category |
| --- | --- | --- |
| `Not Shortlisted / Rejected` | 9 | `rejected` |
| `Application Submitted` | 9 | `pending` |
| `No Change` | 2 | `pending` |
| `Assessment Completed & Submitted` | 1 | `interview` |
| `Assessment Invitation Received` | 1 | `interview` |
| `Drive Announcement Received` | 1 | `pending` |
| `Applied` | 1 | `pending` |
| `Rejected` | 1 | `rejected` |
| **Total** | **25** | |

Two notes on judgement calls:

- **`No Change` → `pending`.** It records that an application is still open with
  no outcome. It is deliberately *not* counted as rejected.
- **`Drive Announcement Received` → `pending`.** A drive was announced but you
  have not yet applied, so it is an open item rather than a submission.

Because categories are exhaustive and mutually exclusive,
`pending + interview + rejected + offer + other == total_applications` always
holds, so the dashboard numbers always reconcile.

The API exposes the mapping so the frontend never has to guess:
`status_categories` maps every observed status to its category and count.

### Duplicate detection

Analytics count **unique** applications. Records are matched against the
strongest key both rows can supply, in this order:

1. `tracking_key` — written by the n8n workflow, authoritative.
2. `company + role + job_id`
3. `company + role + application_date`
4. `company + role` (weakest fallback)

A weaker tier is only consulted when a stronger one is missing from either row,
so two different tracking keys for the same role are never merged. Every
suppressed duplicate is reported in `duplicate_groups` with the tier that fired,
so nothing disappears silently. Your current 25 records have 25 distinct
tracking keys, so there are 0 duplicates today.

Platform names are grouped case-insensitively, so `Naukri.com` and `naukri.com`
are counted as one platform (currently 3 applications).

---

## 9. How matching works

Matching is a **transparent keyword heuristic, not an AI prediction**. It never
invents eligibility, salary or requirements — it only compares text you already
have.

Your configured interests: AI/ML, Generative AI, LLMs, RAG, Java, Spring Boot,
Backend development, Python, Software engineering, Data science.
Your preferred cities: Bengaluru, Pune, Mumbai, Hyderabad.

Score for one listing:

| Component | Weight | Source |
| --- | --- | --- |
| Skill match | 12 points per interest, capped at 40 | `Required Skills` |
| Title match | 7.5 points per interest, capped at 15 | `Internship Title` (a weaker signal) |
| Location match | 30 points | `Location` vs your preferred cities |

Raw points are normalised against the 85-point maximum, giving a **0–100
score**, then banded:

| Score | Tier |
| --- | --- |
| ≥ 60 | `strong` |
| 40–59.9 | `good` |
| 20–39.9 | `moderate` |
| < 20 | `weak` |

Keywords match on whole-word boundaries, so `ai` does not match inside `mysql`
and `ml` does not match inside `email`. City spelling variants are handled
(`Bangalore` → Bengaluru).

Every match carries its `matched_interests`, `matched_locations` and plain
English `reasons`, so you can always see why something scored what it did.

---

## 10. API endpoints

All endpoints are `GET`, live under `/api`, and are read-only. Interactive docs:
<http://127.0.0.1:8000/docs>.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health, active data source, row counts. |
| GET | `/api/dashboard` | Everything the Dashboard page needs, in one call. |
| GET | `/api/applications` | Paginated applications + optional filters. |
| GET | `/api/jobs` | Paginated listings + optional filters. |
| GET | `/api/analytics/applications` | Status distribution + monthly trend. |
| GET | `/api/analytics/jobs` | Job-market aggregates. |
| GET | `/api/analytics/skills` | Most requested skills. |
| GET | `/api/analytics/matching` | Explainable preference matches. |
| GET | `/api/meta` | Active configuration (no secrets). |

### `GET /api/health`

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{
  "status": "ok",
  "app": "JobPilot API",
  "version": "0.1.0",
  "environment": "development",
  "data_source": "csv",
  "timestamp": "2026-10-18T12:00:00+00:00",
  "checks": {
    "data_source": "csv",
    "applications_rows": 25,
    "applications_unique": 25,
    "job_openings_rows": 0,
    "job_openings_unique": 0,
    "fetched_at": "2026-10-18T12:00:00+00:00",
    "cached": false
  }
}
```

Returns `200` with `"status": "ok"`, or `200` with `"status": "degraded"` and a
`checks.data_error` string when the data source is misconfigured. Note it never
contains file paths or credentials.

### `GET /api/dashboard`

```bash
curl http://127.0.0.1:8000/api/dashboard
```

```json
{
  "applications": {
    "total_applications": 25,
    "status_counts": { "Not Shortlisted / Rejected": 9, "Application Submitted": 9 },
    "status_categories": {
      "Not Shortlisted / Rejected": { "category": "rejected", "count": 9 }
    },
    "category_counts": { "pending": 13, "interview": 2, "rejected": 10, "offer": 0, "other": 0 },
    "unclassified_applications": 0,
    "pending_applications": 13,
    "interview_applications": 2,
    "rejected_applications": 10,
    "offers": 0,
    "active_applications": 15,
    "response_rate_percent": 40.0,
    "applications_by_platform": [{ "platform": "Naukri.com", "count": 3 }],
    "applications_by_type": [
      { "application_type": "Internship", "count": 13 },
      { "application_type": "Full-Time / Entry", "count": 9 },
      { "application_type": "Ambassador", "count": 1 }
    ],
    "applications_over_time": [
      { "month": "2026-08", "count": 7 },
      { "month": "2026-09", "count": 10 },
      { "month": "2026-10", "count": 4 }
    ],
    "recent_applications": [
      { "id": 23, "company": "InfoCepts", "status": "Applied" }
    ],
    "missing_data_counts": {
      "application_date": 4,
      "application_type": 2,
      "job_id": 12,
      "latest_update_date": 2,
      "notes": 1,
      "platform": 2
    },
    "duplicate_groups": [],
    "generated_at": "2026-10-18T12:00:00+00:00"
  },
  "jobs": {
    "total_listings": 0,
    "listings_by_location": [],
    "listings_by_company": [],
    "listings_by_work_arrangement": [],
    "top_skills": [],
    "listings_by_verification_status": [],
    "missing_data_counts": {},
    "duplicate_groups": [],
    "generated_at": "2026-10-18T12:00:00+00:00"
  },
  "top_matches": [],
  "source": "csv",
  "data_freshness": "just now",
  "cached": false,
  "fetched_at": "2026-10-18T12:00:00+00:00"
}
```

### `GET /api/applications`

| Query param | Type | Notes |
| --- | --- | --- |
| `status` | string | Case-insensitive substring on the raw status, **or** an exact category (`pending`, `interview`, `rejected`, `offer`, `other`). |
| `platform` | string | Case-insensitive substring. |
| `company` | string | Case-insensitive substring. |
| `page` | int ≥ 1 | Defaults to 1. |
| `page_size` | int ≥ 1 | Clamped to `MAX_PAGE_SIZE` (200). |

```bash
curl "http://127.0.0.1:8000/api/applications?status=Rejected&page=1&page_size=5"
curl "http://127.0.0.1:8000/api/applications?platform=naukri"
```

```json
{
  "items": [
    {
      "id": 3,
      "company": "Icertis",
      "role": "Intern, Development",
      "application_type": "Internship",
      "application_date": "2026-09-17",
      "latest_update_date": "2026-10-12",
      "status": "Not Shortlisted / Rejected",
      "status_category": "rejected",
      "job_id": "7561",
      "platform": "Icertis Candidate Self-Service Page (Oracle Cloud HCM)",
      "notes": null,
      "tracking_key": "icertis|id:7561",
      "has_application_date": true,
      "duplicate_count": 1
    }
  ],
  "total": 10,
  "page": 1,
  "page_size": 5,
  "total_pages": 2,
  "available_statuses": ["Application Submitted", "Applied", "No Change"],
  "available_platforms": ["Naukri.com", "Ivaluework", "Internshala"]
}
```

`available_statuses` and `available_platforms` are provided so the frontend can
populate filter dropdowns without hardcoding anything.

### `GET /api/jobs`

| Query param | Type | Notes |
| --- | --- | --- |
| `location` | string | Substring match. |
| `skill` | string | Matches any item in the parsed `Required Skills` list. |
| `verification` | string | **Exact**, case-insensitive (`verified` does not match `unverified`). |
| `work_arrangement` | string | Substring match. |
| `min_match_score` | float 0–100 | Minimum heuristic match score. |
| `page`, `page_size` | int | Pagination. |

```bash
curl "http://127.0.0.1:8000/api/jobs?location=Pune"
curl "http://127.0.0.1:8000/api/jobs?skill=Java&min_match_score=40"
```

```json
{
  "items": [
    {
      "id": 1,
      "company": "Infosys",
      "title": "Java Backend Intern",
      "location": "Pune",
      "work_arrangement": "On-site",
      "start_date": "2026-11-01",
      "duration": "6 months",
      "stipend": "25000",
      "eligibility": "B.Tech students",
      "application_deadline": "2026-10-30",
      "required_skills": "Java, Spring Boot, Backend, MySQL",
      "fit_assessment": "Good fit",
      "verification_status": "Verified",
      "application_url": "https://example.invalid/a",
      "source_url": "https://example.invalid/s",
      "date_found": "2026-10-10",
      "unique_job_key": "infosys|java-backend-pune",
      "skills": ["Java", "Spring Boot", "Backend", "MySQL"]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "available_locations": ["Pune"],
  "available_verification_statuses": ["Verified"]
}
```

> The `Job Openings` tab is currently empty, so this endpoint returns
> `{"items": [], "total": 0, "total_pages": 0, ...}` with HTTP `200`. That is
> the correct behaviour — no placeholder listings are ever generated.

### `GET /api/analytics/applications`

```bash
curl http://127.0.0.1:8000/api/analytics/applications
```

Returns the `applications` block shown under `/api/dashboard` (with 5 recent
applications). Same shape, so one component can render both.

### `GET /api/analytics/jobs`

```bash
curl http://127.0.0.1:8000/api/analytics/jobs
```

Returns the `jobs` block. Safe with zero listings.

### `GET /api/analytics/skills`

| Query param | Type | Notes |
| --- | --- | --- |
| `limit` | int 1–100 | Default 20. |
| `min_count` | int ≥ 1 | Only skills requested by at least N listings. |

```bash
curl "http://127.0.0.1:8000/api/analytics/skills?limit=10&min_count=1"
```

```json
{
  "total_listings": 4,
  "total_skill_mentions": 12,
  "unique_skills": 11,
  "skills": [{ "skill": "Java", "count": 1 }, { "skill": "Spring Boot", "count": 1 }],
  "min_count": 1,
  "generated_at": "2026-10-18T12:00:00+00:00"
}
```

### `GET /api/analytics/matching`

| Query param | Type | Notes |
| --- | --- | --- |
| `limit` | int 1–50 | Default 20. |
| `min_score` | float 0–100 | Default 0. |
| `include_unmatched` | bool | Also return zero-score listings. Default `false`. |

```bash
curl "http://127.0.0.1:8000/api/analytics/matching?min_score=40"
```

```json
{
  "matches": [
    {
      "job_id": 1,
      "company": "Infosys",
      "title": "Java Backend Intern",
      "location": "Pune",
      "work_arrangement": "On-site",
      "required_skills": ["Java", "Spring Boot", "Backend", "MySQL"],
      "verification_status": "Verified",
      "application_url": "https://example.invalid/a",
      "score": 77.6,
      "tier": "strong",
      "matched_interests": ["Java", "Spring Boot", "Backend development"],
      "matched_locations": ["Pune"],
      "reasons": [
        "Required skills match: Backend development, Java, Spring Boot",
        "Preferred city: Pune"
      ]
    }
  ],
  "total_listings": 4,
  "matched_listings": 1,
  "min_score": 40.0,
  "include_unmatched": false,
  "interests": ["AI/ML", "Backend development", "Data science", "Generative AI"],
  "preferred_locations": ["Bengaluru", "Hyderabad", "Mumbai", "Pune"],
  "scoring_note": "Heuristic, not an AI prediction: up to 40 points for interests found in Required Skills, up to 15 points for the same interests in the job title, and 30 points for a preferred city.",
  "generated_at": "2026-10-18T12:00:00+00:00"
}
```

### Status codes and error handling

| Code | When |
| --- | --- |
| `200` | Success. |
| `422` | Invalid query parameter (bad `page`, over-long filter, out-of-range score). |
| `404` | Unknown route. |
| `503` | The configured data source failed (missing file, Sheets auth/quota/tab error). |
| `500` | Unexpected error — logged server-side, generic message returned. |

Error bodies are always `{"detail": "..."}`. Stack traces, file paths and
credentials are never included.

---

## 11. Frontend readiness

The responses above are the contract for the planned React pages:

| Page | Endpoint(s) |
| --- | --- |
| Dashboard | `GET /api/dashboard` |
| Find Jobs | `GET /api/jobs`, `GET /api/analytics/matching` |
| My Applications | `GET /api/applications` |
| Analytics | `GET /api/analytics/applications`, `/api/analytics/jobs`, `/api/analytics/skills` |
| AI Assistant (future) | Not built yet — intended to be backed by Gemini through n8n, calling this API only for context. |

CORS is enabled for the local frontend origin via `CORS_ORIGINS`, defaulting to
`http://localhost:3000`. Only `GET` and `OPTIONS` are allowed, and credentials
are not permitted (there is no auth in this project). Add your real origin when
you deploy:

```dotenv
CORS_ORIGINS=http://localhost:3000,https://your-app.vercel.app
```

Timestamps are timezone-aware ISO 8601 in UTC. Nullable fields are always
present as `null` rather than omitted, so TypeScript types can be non-optional.

---

## 12. Troubleshooting

**`Activate.ps1` is blocked by the execution policy**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**`Data file not found: applications.csv` (HTTP 503)**

The app cannot find the CSVs. Check that `backend/data/applications.csv` exists
and that `DATA_DIR` resolves correctly. Relative `DATA_DIR` values are resolved
from `backend/`, so `data` means `backend/data`.

**`/api/health` says `degraded`**

Read `checks.data_error` — it names the exact problem (missing
`GOOGLE_SHEETS_SPREADSHEET_ID`, missing credentials file, wrong tab name, quota).
For CSV mode it is almost always a missing or unparseable file.

**`Tab 'Applications' was not found`**

Your Applications tab is probably still named `Sheet1`. Set:

```dotenv
GOOGLE_SHEETS_APPLICATIONS_TAB=Sheet1
```

The backend never renames a tab — it only reads whatever name you configure.

**Google Sheets returns a 404 / permission error**

The service account has not been shared on the spreadsheet. Open the sheet →
**Share** → add the service account's `client_email` as Viewer or Editor.

**Google Sheets returns a 401 / `invalid_grant`**

The key file is wrong, malformed, or was rotated in Google Cloud. Re-download
the JSON key and update `GOOGLE_APPLICATION_CREDENTIALS`.

**`403` / quota exceeded**

Lower `SHEETS_CACHE_TTL_SECONDS` pressure by *raising* the TTL (e.g. `600`), or
switch back to `DATA_SOURCE=csv` while you wait for the quota to reset.

**Total applications does not match the spreadsheet**

`total_applications` counts **unique** records, and unknown statuses go to
`other` rather than being guessed. The five categories always sum to the total,
so any gap means rows were merged as duplicates — inspect `duplicate_groups` to
see which tier fired.

**`/api/jobs` is always empty**

Expected until n8n starts writing rows into the `Job Openings` tab. The backend
never creates placeholder listings.

**Tests fail with `ModuleNotFoundError: No module named 'app'`**

Run pytest from the `backend` folder — `pyproject.toml` sets
`pythonpath = ["."]`.

**Port 8000 already in use**

```powershell
python -m uvicorn app.main:app --reload --port 8080
```