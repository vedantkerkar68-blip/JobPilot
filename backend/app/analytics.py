"""Analytics for JobPilot: application tracking, job-market stats and matching.

Everything in this module is a pure function over the two normalised
:class:`pandas.DataFrame` objects produced by :mod:`app.sheets`.  No I/O, no
network, no state.

Status categorisation
---------------------
JobPilot never guesses that an unfamiliar status means "rejected" or "pending".
Each status string is matched against an ordered rule table
(:data:`STATUS_RULES`) on whole-word boundaries.  If nothing matches, the
status is categorised as ``"other"`` and is counted separately, so
``pending + interview + rejected + offer + other == total`` always holds and no
application is silently lost or double-counted.

The rule table (first match wins) is:

======  =========================================================  ==========
Order   Matched keywords                                             Category
======  =========================================================  ==========
1       offer, offer letter, hired, selected, accepted, onboarded    ``offer``
2       reject, rejected, not shortlisted, not selected, declined,   ``rejected``
        unsuccessful, did not select, closed,
        no longer under consideration, not moving forward
3       interview, assessment, oa, aptitude, test, scheduled,        ``interview``
        shortlisted for, round, rounds, group discussion, gd,
        hr screen, hiring
4       submitted, applied, awaiting, in progress, in process,      ``pending``
        pending, no change, drive, registered, invited,
        under review, screening
======  =========================================================  ==========

Order matters: ``"Assessment Completed & Submitted"`` hits rule 3
(``assessment``) before rule 4 (``submitted``), so it is treated as an active
interview-stage application rather than a pending one.

For the statuses currently in the spreadsheet the mapping resolves to:

======================================  ==================
Status                                  Category
======================================  ==================
``Application Submitted``               ``pending``
``No Change``                           ``pending``
``Drive Announcement Received``         ``pending``
``Applied``                             ``pending``
``Assessment Invitation Received``      ``interview``
``Assessment Completed & Submitted``     ``interview``
``Not Shortlisted / Rejected``          ``rejected``
``Rejected``                            ``rejected``
======================================  ==================

Matching
--------
:func:`score_job_match` is a transparent keyword heuristic, not an AI
prediction.  See that function's docstring for the exact weights; every score
is accompanied by the reasons that produced it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .sheets import Dataset, is_missing

# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #

#: Mutually exclusive status categories. ``other`` catches unknown statuses.
PENDING = "pending"
INTERVIEW = "interview"
REJECTED = "rejected"
OFFER = "offer"
OTHER = "other"

#: Ordering used whenever categories are listed.
CATEGORY_ORDER: tuple[str, ...] = (PENDING, INTERVIEW, REJECTED, OFFER, OTHER)

#: Keywords per category, evaluated in order (first match wins).
STATUS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        OFFER,
        ("offer", "offer letter", "hired", "selected", "accepted", "onboarded"),
    ),
    (
        REJECTED,
        (
            "reject",
            "rejected",
            "not shortlisted",
            "not selected",
            "declined",
            "unsuccessful",
            "did not select",
            "no longer under consideration",
            "not moving forward",
            "closed",
        ),
    ),
    (
        INTERVIEW,
        (
            "interview",
            "assessment",
            "oa",
            "aptitude",
            "test",
            "scheduled",
            "shortlisted for",
            "round",
            "rounds",
            "group discussion",
            "gd",
            "hr screen",
            "hiring",
        ),
    ),
    (
        PENDING,
        (
            "submitted",
            "applied",
            "awaiting",
            "in progress",
            "in process",
            "pending",
            "no change",
            "drive",
            "registered",
            "invited",
            "under review",
            "screening",
        ),
    ),
)


def categorise_status(status: Any) -> str:
    """Map one status string onto a category.

    Args:
        status: Raw status text, possibly ``None`` or a placeholder.

    Returns:
        One of :data:`CATEGORY_ORDER`.  Unknown or missing statuses return
        ``"other"`` — they are never guessed into pending or rejected.
    """
    if is_missing(status):
        return OTHER

    text = str(status).strip().lower()
    for category, keywords in STATUS_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return OTHER


_WORD_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile (and cache) a whole-word pattern for one keyword."""
    pattern = _WORD_BOUNDARY_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])")
        _WORD_BOUNDARY_CACHE[keyword] = pattern
    return pattern


def _matches_any(text: str, keywords: Iterable[str]) -> bool:
    """Return ``True`` when any keyword appears in ``text`` on word boundaries.

    Matching on word boundaries avoids false positives such as ``"ai"``
    inside ``"mysql"`` or ``"ml"`` inside ``"email"``.
    """
    lowered = text.lower()
    return any(_keyword_pattern(keyword).search(lowered) for keyword in keywords if keyword)


# --------------------------------------------------------------------------- #
# Matching profile
# --------------------------------------------------------------------------- #

#: User's target interests, each with the keywords that signal it.
#: Keywords are matched on whole-word boundaries, so "ai" does not match inside
#: "mysql" and "ml" does not match inside "email".
INTEREST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI/ML": ("ai", "ml", "ai/ml", "artificial intelligence", "machine learning"),
    "Generative AI": ("generative ai", "genai", "gen ai"),
    "LLMs": ("llm", "llms", "large language model", "gpt", "foundation model"),
    "RAG": ("rag", "retrieval augmented", "retrieval-augmented", "vector database"),
    "Java": ("java",),
    "Spring Boot": ("spring boot", "springboot", "spring-boot"),
    "Backend development": (
        "backend",
        "back-end",
        "back end",
        "api development",
        "microservices",
        "microservice",
    ),
    "Python": ("python",),
    "Software engineering": ("software engineer", "software engineering", "sde", "developer"),
    "Data science": ("data science", "data scientist", "analytics", "statistics"),
}

#: Preferred Indian cities, each with spelling variants seen on job portals.
PREFERRED_LOCATIONS: dict[str, tuple[str, ...]] = {
    "Bengaluru": ("bengaluru", "bangalore", "blr"),
    "Pune": ("pune", "pimpri", "hinjewadi", "kharadi"),
    "Mumbai": ("mumbai", "bombay", "powai", "thane"),
    "Hyderabad": ("hyderabad", "hyderguda", "kondapur", "hitec"),
}

# --- Scoring weights --------------------------------------------------------
# Raw points are capped per component, then normalised so a perfect match
# (every component maxed out) is exactly 100.

#: Points per interest found in ``Required Skills``.
SKILL_POINTS_PER_INTEREST = 12.0
#: Maximum raw points from skills alone (reached at 4 matching interests).
SKILL_CAP = 40.0
#: Points per interest found only in the job title (a weaker signal).
TITLE_POINTS_PER_INTEREST = 7.5
#: Maximum raw points from the title.
TITLE_CAP = 15.0
#: Raw points for a listing in a preferred city.
LOCATION_POINTS = 30.0

#: Maximum achievable raw score: 40 + 15 + 30.
MAX_RAW_SCORE = SKILL_CAP + TITLE_CAP + LOCATION_POINTS

#: Score bands used to label a match.
MATCH_TIERS: tuple[tuple[float, str], ...] = (
    (60.0, "strong"),
    (40.0, "good"),
    (20.0, "moderate"),
    (0.0, "weak"),
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    """Return a trimmed single-line string, or ``""`` for missing values."""
    if is_missing(value):
        return ""
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def display_label(value: Any) -> str | None:
    """Return a presentable label, or ``None`` when the value is missing."""
    text = clean_text(value)
    return text or None


def _frame_or_empty(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Return ``frame`` or an empty DataFrame when ``None`` was passed."""
    return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return a column as an object Series, empty when the column is absent."""
    if column in frame.columns:
        return frame[column].astype("object")
    return pd.Series([None] * len(frame), index=frame.index, dtype="object")


def _normalise_key(value: Any) -> str:
    """Lowercase, collapse whitespace and strip separators from a key part."""
    text = clean_text(value).lower()
    return re.sub(r"[\s_]+", " ", text).strip()


def _date_or_none(value: Any) -> datetime | None:
    """Convert a pandas timestamp to a timezone-aware UTC ``datetime``."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError):
        return None
    if stamp is pd.NaT or pd.isna(stamp):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.to_pydatetime()


def _iso_or_none(value: Any) -> str | None:
    """Render a date cell as an ISO ``YYYY-MM-DD`` string, or ``None``."""
    parsed = _date_or_none(value)
    return parsed.date().isoformat() if parsed else None


def _counter_to_rows(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    """Turn a ``Counter`` into ``[{key: label, "count": n}]``, largest first."""
    return [
        {key: label, "count": int(count)}
        for label, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _normalised_counter(values: Iterable[Any]) -> Counter[str]:
    """Count values case-insensitively, returning the most common spelling.

    ``"Naukri.com"`` and ``"naukri.com"`` are the same portal, so they must not
    appear as two separate platforms.
    """
    buckets: dict[str, Counter[str]] = {}
    for value in values:
        label = clean_text(value)
        if not label:
            continue
        buckets.setdefault(_normalise_key(label), Counter())[label] += 1

    merged: Counter[str] = Counter()
    for variants in buckets.values():
        merged[variants.most_common(1)[0][0]] += sum(variants.values())
    return merged


# --------------------------------------------------------------------------- #
# Applications: deduplication and record building
# --------------------------------------------------------------------------- #

#: Candidate duplicate-detection keys, tried strongest-first.
#: 1. Tracking Key (authoritative, written by the n8n workflow).
#: 2. Company + Role + Job ID.
#: 3. Company + Role + Application Date.
#: 4. Company + Role (weakest — catches the same role applied twice).
DUPLICATE_KEY_TIERS: tuple[str, ...] = (
    "tracking_key",
    "company_role_job_id",
    "company_role_date",
    "company_role",
)


def _row_keys(row: Mapping[str, Any]) -> dict[str, str | None]:
    """Build the candidate duplicate-detection keys for one row."""
    company = _normalise_key(row.get("company"))
    role = _normalise_key(row.get("role"))
    job_id = _normalise_key(row.get("job_id"))
    application_date = _normalise_key(row.get("application_date"))

    def join(*parts: str) -> str | None:
        if not any(parts):
            return None
        return "|".join(part for part in parts if part)

    tracking = _normalise_key(row.get("tracking_key")) or None
    role_date = join(company, role, application_date)
    role_job = join(company, role, job_id)
    role_only = join(company, role)

    return {
        "tracking_key": tracking,
        "company_role_job_id": role_job if job_id else None,
        "company_role_date": role_date if application_date else None,
        "company_role": role_only,
    }


def deduplicate_records(records: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split records into first-occurrences and duplicates.

    For each record the tiers in :data:`DUPLICATE_KEY_TIERS` are tried in order.
    The **strongest tier that both records can supply** decides: if the two keys
    match, the record is a duplicate of the earlier one; if they differ, the
    record is genuinely new and no weaker tier is consulted.  A weaker tier is
    only consulted when a stronger one is missing from either record.

    Args:
        records: Normalised application or job records.

    Returns:
        ``(unique_records, duplicate_groups)`` where each duplicate group is
        ``{"key_tier": ..., "key": ..., "count": n}``.
    """
    unique: list[dict[str, Any]] = []
    seen: dict[str, set[str]] = {tier: set() for tier in DUPLICATE_KEY_TIERS}
    duplicate_groups: Counter[tuple[str, str]] = Counter()

    for record in records:
        keys = _row_keys(record)

        matched_tier: str | None = None
        matched_key: str | None = None
        for tier in DUPLICATE_KEY_TIERS:
            key = keys.get(tier)
            if not key:
                # This tier is unavailable for this record; try a weaker one.
                continue
            if key in seen[tier]:
                matched_tier, matched_key = tier, key
            # Either way this was the strongest usable tier, so stop here.
            break

        if matched_tier is not None:
            duplicate_groups[(matched_tier, matched_key or "")] += 1
            unique[-1]["_duplicate_count"] = unique[-1].get("_duplicate_count", 1) + 1
            continue

        for tier in DUPLICATE_KEY_TIERS:
            key = keys.get(tier)
            if key:
                seen[tier].add(key)

        record["_duplicate_count"] = 1
        unique.append(record)

    duplicates = [
        {"key_tier": tier, "key": key, "count": int(count)}
        for (tier, key), count in sorted(
            duplicate_groups.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    return unique, duplicates


def build_application_records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Convert the applications DataFrame into unique, JSON-ready dicts.

    Rows are de-duplicated first, so downstream counts cannot double-count.

    Args:
        frame: Normalised applications DataFrame, possibly empty.

    Returns:
        One dict per unique application.
    """
    records, _ = _application_records_with_duplicates(frame)
    for index, record in enumerate(records, start=1):
        record["id"] = index
    return records


def _application_records_with_duplicates(
    frame: pd.DataFrame | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build application records and report the duplicate groups found.

    Returns:
        ``(unique_records, duplicate_groups)``.
    """
    frame = _frame_or_empty(frame)
    if frame.empty:
        return [], []

    columns = {
        "company": _series(frame, "company"),
        "role": _series(frame, "role"),
        "application_type": _series(frame, "application_type"),
        "application_date": _series(frame, "application_date"),
        "latest_update_date": _series(frame, "latest_update_date"),
        "status": _series(frame, "status"),
        "job_id": _series(frame, "job_id"),
        "platform": _series(frame, "platform"),
        "notes": _series(frame, "notes"),
        "tracking_key": _series(frame, "tracking_key"),
    }

    records: list[dict[str, Any]] = []
    for position in range(len(frame)):
        row = {name: series.iloc[position] for name, series in columns.items()}
        status_text = clean_text(row["status"]) or None
        records.append(
            {
                "id": position + 1,
                "company": display_label(row["company"]),
                "role": display_label(row["role"]),
                "application_type": display_label(row["application_type"]),
                "application_date": _iso_or_none(row["application_date"]),
                "latest_update_date": _iso_or_none(row["latest_update_date"]),
                "status": status_text,
                "status_category": categorise_status(row["status"]),
                "job_id": display_label(row["job_id"]),
                "platform": display_label(row["platform"]),
                "notes": display_label(row["notes"]),
                "tracking_key": display_label(row["tracking_key"]),
                "has_application_date": _date_or_none(row["application_date"]) is not None,
                "duplicate_count": 1,
            }
        )

    return deduplicate_records(records)


# --------------------------------------------------------------------------- #
# Application analytics
# --------------------------------------------------------------------------- #


def application_analytics(
    frame: pd.DataFrame | None,
    *,
    recent_limit: int = 10,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute the full application analytics block.

    Args:
        frame: Normalised applications DataFrame.
        recent_limit: How many recent applications to return.
        now: Injectable clock (UTC) so tests are deterministic.

    Returns:
        A dict with totals, status distribution, category counts, platform
        breakdown, monthly trend, recent applications, missing-data counts and
        duplicate groups.
    """
    now = now or datetime.now(timezone.utc)
    records, duplicate_groups = _application_records_with_duplicates(frame)

    total = len(records)
    status_counter = Counter(record["status"] for record in records if record["status"])
    category_counter = Counter(record["status_category"] for record in records)
    platform_counter = _normalised_counter(record["platform"] for record in records)
    type_counter = _normalised_counter(record["application_type"] for record in records)
    missing_counter = Counter(
        field for record in records for field, value in record.items() if value is None
    )

    category_counts = {category: int(category_counter.get(category, 0)) for category in CATEGORY_ORDER}
    decided = category_counts[REJECTED] + category_counts[OFFER]

    return {
        "total_applications": total,
        "status_counts": dict(sorted(status_counter.items(), key=lambda kv: (-kv[1], kv[0]))),
        "status_categories": _status_category_map(status_counter, category_counter),
        "category_counts": category_counts,
        "unclassified_applications": category_counts[OTHER],
        "pending_applications": category_counts[PENDING],
        "interview_applications": category_counts[INTERVIEW],
        "rejected_applications": category_counts[REJECTED],
        "offers": category_counts[OFFER],
        "active_applications": total - category_counts[REJECTED],
        "response_rate_percent": _percentage(decided, total),
        "applications_by_platform": _counter_to_rows(platform_counter, "platform"),
        "applications_by_type": _counter_to_rows(type_counter, "application_type"),
        "applications_over_time": applications_over_time(records),
        "recent_applications": recent_applications(records, limit=recent_limit),
        "missing_data_counts": dict(sorted(missing_counter.items())),
        "duplicate_groups": duplicate_groups,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
    }


def _status_category_map(
    status_counter: Counter[str], category_counter: Counter[str]
) -> dict[str, dict[str, Any]]:
    """Map every observed status to its category, for API transparency.

    Returns:
        ``{status: {"category": ..., "count": n}}`` sorted by descending count.
    """
    return {
        status: {"category": categorise_status(status), "count": int(count)}
        for status, count in sorted(status_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    }


def _percentage(part: int, whole: int) -> float:
    """Return ``part / whole`` as a rounded percentage, safe when whole is 0."""
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 2)


def applications_over_time(
    source: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Count applications per calendar month (``YYYY-MM``).

    Rows without a parsable application date are excluded, because a month
    cannot be derived from them; ``missing_data_counts`` reports how many those
    were.  When a DataFrame is passed it is de-duplicated first, so a repeated
    row is never counted twice.

    Args:
        source: A normalised applications DataFrame, a list of already
            de-duplicated application records, or ``None``.

    Returns:
        ``[{"month": "YYYY-MM", "count": n}]`` in chronological order.
    """
    if isinstance(source, pd.DataFrame) or source is None:
        records, _ = _application_records_with_duplicates(source)
    else:
        records = list(source)

    dated = [record["application_date"] for record in records if record.get("application_date")]
    if not dated:
        return []

    index = pd.PeriodIndex(pd.to_datetime(pd.Series(dated, dtype="string")), freq="M")
    counts = pd.Series(index.astype(str)).value_counts().sort_index()
    return [{"month": str(month), "count": int(count)} for month, count in counts.items()]


def recent_applications(
    records: Sequence[Mapping[str, Any]], *, limit: int = 10
) -> list[dict[str, Any]]:
    """Return the most recently updated applications, newest first.

    Records without a latest-update date fall back to the application date.
    Records with neither date sort last.
    """
    def sort_key(record: Mapping[str, Any]) -> tuple[str, int]:
        stamp = record.get("latest_update_date") or record.get("application_date") or ""
        return (stamp, int(record.get("id") or 0))

    ordered = sorted(records, key=sort_key, reverse=True)
    return [dict(record) for record in ordered[: max(0, limit)]]


# --------------------------------------------------------------------------- #
# Job openings
# --------------------------------------------------------------------------- #


def build_job_records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Convert the job-openings DataFrame into unique, JSON-ready dicts."""
    records, _ = _job_records_with_duplicates(frame)
    for index, record in enumerate(records, start=1):
        record["id"] = index
    return records


def _job_records_with_duplicates(
    frame: pd.DataFrame | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build job records and report the duplicate groups found.

    Returns:
        ``(unique_records, duplicate_groups)``.
    """
    frame = _frame_or_empty(frame)
    if frame.empty:
        return [], []

    fields = (
        "company",
        "title",
        "location",
        "work_arrangement",
        "start_date",
        "duration",
        "stipend",
        "eligibility",
        "application_deadline",
        "required_skills",
        "fit_assessment",
        "verification_status",
        "application_url",
        "source_url",
        "date_found",
        "unique_job_key",
    )
    columns = {name: _series(frame, name) for name in fields}

    records: list[dict[str, Any]] = []
    for position in range(len(frame)):
        row = {name: series.iloc[position] for name, series in columns.items()}
        skills = clean_text(row["required_skills"])
        record = {name: display_label(row[name]) for name in fields}
        record.update(
            {
                "id": position + 1,
                "skills": _split_skills(skills),
                "start_date": _iso_or_none(row["start_date"]),
                "application_deadline": _iso_or_none(row["application_deadline"]),
                "date_found": _iso_or_none(row["date_found"]),
                "verification_status": clean_text(row["verification_status"]) or "unverified",
            }
        )
        records.append(record)

    unique, duplicates = deduplicate_records(records)
    return unique, duplicates


def _split_skills(value: Any) -> list[str]:
    """Split a ``Required Skills`` cell into a clean list of skills."""
    text = clean_text(value)
    if not text:
        return []
    parts = re.split(r"[,;/|]| and ", text)
    return [part.strip() for part in parts if part.strip()]


def job_analytics(frame: pd.DataFrame | None, *, now: datetime | None = None) -> dict[str, Any]:
    """Compute job-market analytics.

    Handles the zero-listing case by returning empty lists and zero totals
    rather than raising or inventing placeholder listings.
    """
    now = now or datetime.now(timezone.utc)
    records, duplicate_groups = _job_records_with_duplicates(frame)
    total = len(records)

    if total == 0:
        return {
            "total_listings": 0,
            "listings_by_location": [],
            "listings_by_company": [],
            "listings_by_work_arrangement": [],
            "top_skills": [],
            "listings_by_verification_status": [],
            "missing_data_counts": {},
            "duplicate_groups": [],
            "generated_at": now.astimezone(timezone.utc).isoformat(),
        }

    location_counter = _normalised_counter(record["location"] for record in records)
    company_counter = _normalised_counter(record["company"] for record in records)
    arrangement_counter = _normalised_counter(record["work_arrangement"] for record in records)
    verification_counter = Counter(
        record["verification_status"] or "unverified" for record in records
    )
    skill_counter = Counter(
        skill for record in records for skill in record["skills"]
    )
    missing_counter = Counter(
        field
        for record in records
        for field, value in record.items()
        if value is None and field != "skills"
    )

    return {
        "total_listings": total,
        "listings_by_location": _counter_to_rows(location_counter, "location"),
        "listings_by_company": _counter_to_rows(company_counter, "company"),
        "listings_by_work_arrangement": _counter_to_rows(arrangement_counter, "work_arrangement"),
        "top_skills": _counter_to_rows(skill_counter, "skill"),
        "listings_by_verification_status": _counter_to_rows(
            verification_counter, "verification_status"
        ),
        "missing_data_counts": dict(sorted(missing_counter.items())),
        "duplicate_groups": duplicate_groups,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# Preference-based matching (heuristic, explainable)
# --------------------------------------------------------------------------- #


def score_job_match(
    record: Mapping[str, Any],
    *,
    interests: Mapping[str, Sequence[str]] | None = None,
    preferred_locations: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Score one job listing against the user's preferences.

    The score is a transparent weighted sum, not an AI prediction:

    * up to 40 raw points for interests found in ``Required Skills``
      (12 points each, capped at four matches);
    * up to 15 raw points (7.5 each) for the same interests in the job title;
    * 30 raw points for a preferred city.

    Raw points are normalised against the 85-point maximum, so the result is a
    0-100 score where a perfect overlap is 100.

    Args:
        record: A job record from :func:`build_job_records`.
        interests: Override for :data:`INTEREST_KEYWORDS`.
        preferred_locations: Override for :data:`PREFERRED_LOCATIONS`.

    Returns:
        A dict with ``score`` (0-100), ``tier``, the matched interests and
        locations, and human-readable ``reasons``.
    """
    interests = interests or INTEREST_KEYWORDS
    preferred_locations = preferred_locations or PREFERRED_LOCATIONS

    skills_text = " , ".join(record.get("skills") or [])
    title_text = clean_text(record.get("title"))
    location_text = clean_text(record.get("location"))

    matched_skills: list[str] = []
    matched_titles: list[str] = []
    for interest, keywords in interests.items():
        if _matches_any(skills_text, keywords):
            matched_skills.append(interest)
        elif _matches_any(title_text, keywords):
            matched_titles.append(interest)

    matched_locations = [
        city for city, variants in preferred_locations.items() if _matches_any(location_text, variants)
    ]

    skill_points = min(len(matched_skills) * SKILL_POINTS_PER_INTEREST, SKILL_CAP)
    title_points = min(len(matched_titles) * TITLE_POINTS_PER_INTEREST, TITLE_CAP)
    location_points = LOCATION_POINTS if matched_locations else 0.0

    raw_score = skill_points + title_points + location_points
    score = round(raw_score / MAX_RAW_SCORE * 100, 1)

    reasons: list[str] = []
    if matched_skills:
        reasons.append("Required skills match: " + ", ".join(sorted(matched_skills)))
    if matched_titles:
        reasons.append("Job title matches: " + ", ".join(sorted(matched_titles)))
    if matched_locations:
        reasons.append("Preferred city: " + ", ".join(sorted(matched_locations)))
    if not reasons:
        reasons.append("No preferred skills or cities found in this listing.")

    return {
        "job_id": record.get("id"),
        "company": record.get("company"),
        "title": record.get("title"),
        "location": record.get("location"),
        "work_arrangement": record.get("work_arrangement"),
        "required_skills": record.get("skills") or [],
        "verification_status": record.get("verification_status"),
        "application_url": record.get("application_url"),
        "score": score,
        "tier": _match_tier(score),
        "matched_interests": sorted(set(matched_skills) | set(matched_titles)),
        "matched_locations": sorted(matched_locations),
        "reasons": reasons,
    }


def _match_tier(score: float) -> str:
    """Map a numeric score onto a human label."""
    for threshold, label in MATCH_TIERS:
        if score >= threshold:
            return label
    return "weak"


def match_jobs(
    frame: pd.DataFrame | None,
    *,
    limit: int = 20,
    min_score: float = 0.0,
    include_unmatched: bool = False,
) -> list[dict[str, Any]]:
    """Score every available listing and return the best matches first.

    Args:
        frame: Normalised job-openings DataFrame.
        limit: Maximum number of matches to return.
        min_score: Drop matches below this score.
        include_unmatched: Keep zero-score listings in the results.

    Returns:
        Match dicts sorted by descending score.  Empty when there are no
        listings; no listing is ever fabricated.
    """
    records = build_job_records(frame)
    matches = [score_job_match(record) for record in records]

    if not include_unmatched:
        matches = [match for match in matches if match["score"] >= min_score and match["score"] > 0]
    else:
        matches = [match for match in matches if match["score"] >= min_score]

    matches.sort(key=lambda match: (-float(match["score"]), str(match["company"] or "")))
    return matches[: max(0, limit)]


def top_skills(
    frame: pd.DataFrame | None, *, limit: int = 20, min_count: int = 1
) -> list[dict[str, Any]]:
    """Return the most frequently requested skills across listings."""
    records = build_job_records(frame)
    counter = Counter(skill for record in records for skill in record["skills"])
    rows = [
        {"skill": skill, "count": int(count)}
        for skill, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        if count >= min_count
    ]
    return rows[: max(0, limit)]


# --------------------------------------------------------------------------- #
# Dashboard aggregation
# --------------------------------------------------------------------------- #


@dataclass
class DashboardSummary:
    """Everything ``GET /api/dashboard`` needs, computed in one pass."""

    applications: dict[str, Any] = field(default_factory=dict)
    jobs: dict[str, Any] = field(default_factory=dict)
    top_matches: list[dict[str, Any]] = field(default_factory=list)
    source: str = "csv"
    fetched_at: datetime | None = None
    cached: bool = False

    @property
    def data_freshness(self) -> str:
        """Human-readable freshness of the underlying snapshot."""
        if self.fetched_at is None:
            return "unknown"
        age = datetime.now(timezone.utc) - self.fetched_at
        seconds = max(0, int(age.total_seconds()))
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60} min ago"
        return f"{seconds // 3600} h ago"


def build_dashboard(
    dataset: Dataset,
    *,
    recent_limit: int = 5,
    match_limit: int = 5,
    now: datetime | None = None,
) -> DashboardSummary:
    """Build the dashboard summary from a dataset snapshot."""
    now = now or dataset.fetched_at or datetime.now(timezone.utc)
    return DashboardSummary(
        applications=application_analytics(
            dataset.applications, recent_limit=recent_limit, now=now
        ),
        jobs=job_analytics(dataset.job_openings, now=now),
        top_matches=match_jobs(dataset.job_openings, limit=match_limit),
        source=dataset.source,
        fetched_at=dataset.fetched_at,
        cached=dataset.cached,
    )


__all__ = [
    "CATEGORY_ORDER",
    "DUPLICATE_KEY_TIERS",
    "DashboardSummary",
    "INTEREST_KEYWORDS",
    "INTERVIEW",
    "OFFER",
    "OTHER",
    "PENDING",
    "PREFERRED_LOCATIONS",
    "REJECTED",
    "STATUS_RULES",
    "application_analytics",
    "applications_over_time",
    "build_application_records",
    "build_dashboard",
    "build_job_records",
    "categorise_status",
    "clean_text",
    "deduplicate_records",
    "job_analytics",
    "match_jobs",
    "recent_applications",
    "score_job_match",
    "top_skills",
]