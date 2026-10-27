"""Pydantic response models for the JobPilot API.

These models are the stable contract the React + TypeScript frontend will code
against (Dashboard, Find Jobs, My Applications, Analytics pages).  They only
describe JSON that already exists; no field here is derived from data the
backend does not actually have.

All models use ``extra="ignore"`` on input-like shapes and default to ``None``
for optional values so an incomplete spreadsheet never breaks serialisation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StatusCategory = Literal["pending", "interview", "rejected", "offer", "other"]


class _Base(BaseModel):
    """Shared model config: ignore unknown keys, read by field name."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# --------------------------------------------------------------------------- #
# Shared shapes
# --------------------------------------------------------------------------- #


class CountItem(_Base):
    """A ``label``/``count`` pair used by every distribution chart."""

    count: int = Field(..., description="Number of records in this bucket.")


class PlatformCount(CountItem):
    """Applications grouped by platform."""

    platform: str


class TypeCount(CountItem):
    """Applications grouped by application type."""

    application_type: str


class MonthCount(CountItem):
    """Applications grouped by calendar month."""

    month: str = Field(..., description="Month bucket in ``YYYY-MM`` format.")


class LocationCount(CountItem):
    """Listings grouped by location."""

    location: str


class CompanyCount(CountItem):
    """Listings grouped by company."""

    company: str


class WorkArrangementCount(CountItem):
    """Listings grouped by work arrangement."""

    work_arrangement: str


class SkillCount(CountItem):
    """A frequently requested skill."""

    skill: str


class VerificationCount(CountItem):
    """Listings grouped by verification status."""

    verification_status: str


class DuplicateGroup(_Base):
    """A group of records judged to describe the same application/listing."""

    key_tier: str = Field(..., description="Which matching rule fired.")
    key: str = Field(..., description="The normalised key that matched.")
    count: int = Field(..., ge=1, description="Duplicate records in this group.")


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #


class ApplicationRecord(_Base):
    """One tracked application, exactly as stored in the spreadsheet."""

    id: int
    company: str | None = None
    role: str | None = None
    application_type: str | None = None
    application_date: str | None = Field(None, description="ISO ``YYYY-MM-DD``.")
    latest_update_date: str | None = Field(None, description="ISO ``YYYY-MM-DD``.")
    status: str | None = Field(None, description="Raw status text from the sheet.")
    status_category: StatusCategory = Field(
        ..., description="Category derived from the status rules."
    )
    job_id: str | None = None
    platform: str | None = None
    notes: str | None = None
    tracking_key: str | None = None
    has_application_date: bool = False
    duplicate_count: int = Field(1, ge=1)


class ApplicationListResponse(_Base):
    """Paginated ``GET /api/applications`` payload."""

    items: list[ApplicationRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
    available_statuses: list[str] = Field(
        default_factory=list, description="Distinct statuses, for filter dropdowns."
    )
    available_platforms: list[str] = Field(
        default_factory=list, description="Distinct platforms, for filter dropdowns."
    )


class StatusCategoryInfo(_Base):
    """One observed status and the category it was mapped to."""

    category: StatusCategory
    count: int = 0


class ApplicationAnalytics(_Base):
    """Everything ``GET /api/analytics/applications`` returns."""

    total_applications: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    status_categories: dict[str, StatusCategoryInfo] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    unclassified_applications: int = 0
    pending_applications: int = 0
    interview_applications: int = 0
    rejected_applications: int = 0
    offers: int = 0
    active_applications: int = 0
    response_rate_percent: float = 0.0
    applications_by_platform: list[PlatformCount] = Field(default_factory=list)
    applications_by_type: list[TypeCount] = Field(default_factory=list)
    applications_over_time: list[MonthCount] = Field(default_factory=list)
    recent_applications: list[ApplicationRecord] = Field(default_factory=list)
    missing_data_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    generated_at: str


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #


class JobRecord(_Base):
    """One discovered internship listing, exactly as stored in the sheet."""

    id: int
    company: str | None = None
    title: str | None = None
    location: str | None = None
    work_arrangement: str | None = None
    start_date: str | None = None
    duration: str | None = None
    stipend: str | None = None
    eligibility: str | None = None
    application_deadline: str | None = None
    required_skills: str | None = None
    fit_assessment: str | None = None
    verification_status: str = "unverified"
    application_url: str | None = None
    source_url: str | None = None
    date_found: str | None = None
    unique_job_key: str | None = None
    skills: list[str] = Field(default_factory=list)


class JobListResponse(_Base):
    """Paginated ``GET /api/jobs`` payload."""

    items: list[JobRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
    available_locations: list[str] = Field(default_factory=list)
    available_verification_statuses: list[str] = Field(default_factory=list)


class JobAnalytics(_Base):
    """Job-market summary for the Analytics page."""

    total_listings: int = 0
    listings_by_location: list[LocationCount] = Field(default_factory=list)
    listings_by_company: list[CompanyCount] = Field(default_factory=list)
    listings_by_work_arrangement: list[WorkArrangementCount] = Field(default_factory=list)
    top_skills: list[SkillCount] = Field(default_factory=list)
    listings_by_verification_status: list[VerificationCount] = Field(default_factory=list)
    missing_data_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    generated_at: str


class SkillAnalytics(_Base):
    """``GET /api/analytics/skills`` payload."""

    total_listings: int = 0
    total_skill_mentions: int = 0
    unique_skills: int = 0
    skills: list[SkillCount] = Field(default_factory=list)
    min_count: int = 1
    generated_at: str


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


class JobMatch(_Base):
    """One explainable preference match."""

    job_id: int
    company: str | None = None
    title: str | None = None
    location: str | None = None
    work_arrangement: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    verification_status: str | None = None
    application_url: str | None = None
    score: float = Field(..., ge=0, le=100)
    tier: Literal["strong", "good", "moderate", "weak"] = "weak"
    matched_interests: list[str] = Field(default_factory=list)
    matched_locations: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class MatchingResponse(_Base):
    """``GET /api/analytics/matching`` payload."""

    matches: list[JobMatch] = Field(default_factory=list)
    total_listings: int = 0
    matched_listings: int = 0
    min_score: float = 0.0
    include_unmatched: bool = False
    interests: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    scoring_note: str = Field(
        default=(
            "Heuristic, not an AI prediction: up to 40 points for interests found "
            "in Required Skills, up to 15 points for the same interests in the job "
            "title, and 30 points for a preferred city."
        )
    )
    generated_at: str


# --------------------------------------------------------------------------- #
# Dashboard and health
# --------------------------------------------------------------------------- #


class DashboardResponse(_Base):
    """``GET /api/dashboard`` payload for the Dashboard page."""

    applications: ApplicationAnalytics
    jobs: JobAnalytics
    top_matches: list[JobMatch] = Field(default_factory=list)
    source: str = "csv"
    data_freshness: str = "unknown"
    cached: bool = False
    fetched_at: str | None = None


class HealthResponse(_Base):
    """``GET /api/health`` payload."""

    status: Literal["ok", "degraded"] = "ok"
    app: str
    version: str
    environment: str = "development"
    data_source: str = "csv"
    timestamp: str
    checks: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ApplicationAnalytics",
    "ApplicationListResponse",
    "ApplicationRecord",
    "CompanyCount",
    "CountItem",
    "DashboardResponse",
    "DuplicateGroup",
    "HealthResponse",
    "JobAnalytics",
    "JobListResponse",
    "JobMatch",
    "JobRecord",
    "LocationCount",
    "MatchingResponse",
    "MonthCount",
    "PlatformCount",
    "SkillAnalytics",
    "SkillCount",
    "StatusCategory",
    "StatusCategoryInfo",
    "TypeCount",
    "VerificationCount",
    "WorkArrangementCount",
]