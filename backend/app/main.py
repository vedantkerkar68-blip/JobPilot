"""FastAPI application for JobPilot.

Read-only analytics API over the JobPilot spreadsheet.  Endpoints are grouped
under ``/api`` and return stable JSON for the React frontend.

Security posture:

* No endpoint can write to Google Sheets or to the CSV exports.
* Filesystem paths, credentials and stack traces are never returned; unexpected
  exceptions are converted into a generic 500 body by FastAPI's handlers and the
  detail is logged server-side instead.
* Query parameters are bounded and validated (page sizes, filter lengths).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import analytics as ana
from .config import Settings
from .config import settings as default_settings
from .schemas import (
    ApplicationAnalytics,
    ApplicationListResponse,
    ApplicationRecord,
    DashboardResponse,
    HealthResponse,
    JobAnalytics,
    JobListResponse,
    JobRecord,
    MatchingResponse,
    SkillAnalytics,
)
from .sheets import DataRepository, DataSourceError, Dataset

logger = logging.getLogger("jobpilot.api")

API_PREFIX = "/api"

#: Upper bound on free-text filter values, to avoid silly inputs.
MAX_FILTER_LENGTH = 120

#: Matches longer than this are dropped by the (cheap) ``contains`` filters.
MAX_RECOMMENDED_MATCHES = 50


# --------------------------------------------------------------------------- #
# Application wiring
# --------------------------------------------------------------------------- #


def create_repository(active_settings: Settings) -> DataRepository:
    """Build a :class:`DataRepository` for the given settings."""
    return DataRepository(active_settings)


def create_app(active_settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        active_settings: Settings to use.  Defaults to the module-level
            settings loaded from the environment.  Tests pass their own.

    Returns:
        A configured :class:`fastapi.FastAPI` instance.
    """
    resolved = active_settings or default_settings

    app = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        description=(
            "Read-only analytics API for JobPilot. Sources: local CSV exports "
            "or a read-only Google Sheets spreadsheet."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = resolved
    app.state.repository = create_repository(resolved)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[],
    )

    _register_exception_handlers(app)
    _register_routes(app)
    return app


def get_settings(request: Request) -> Settings:
    """FastAPI dependency returning the active settings."""
    return request.app.state.settings


def get_repository(request: Request) -> DataRepository:
    """FastAPI dependency returning the active data repository."""
    return request.app.state.repository


def get_dataset(repository: Annotated[DataRepository, Depends(get_repository)]) -> Dataset:
    """Load the dataset, translating data-source problems into HTTP errors."""
    try:
        return repository.get_dataset()
    except DataSourceError as exc:
        logger.warning("Data source error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


SettingsDep = Annotated[Settings, Depends(get_settings)]
RepositoryDep = Annotated[DataRepository, Depends(get_repository)]
DatasetDep = Annotated[Dataset, Depends(get_dataset)]


def _register_exception_handlers(app: FastAPI) -> None:
    """Return JSON (never HTML or a stack trace) for error responses."""

    @app.exception_handler(DataSourceError)
    async def _data_source_error(_: Request, exc: DataSourceError) -> JSONResponse:
        logger.warning("Data source error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Log the detail server-side; never leak it or a traceback to the client.
        logger.exception("Unhandled error while serving request: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )


# --------------------------------------------------------------------------- #
# Query helpers
# --------------------------------------------------------------------------- #


def _clean_filter(value: str | None) -> str | None:
    """Normalise an optional free-text filter to ``None`` or a trimmed string."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _page_bounds(total: int, page: int, page_size: int) -> tuple[int, int, int]:
    """Return ``(offset, total_pages, page)`` for a paginated list.

    The page is *not* clamped: requesting a page past the end returns an empty
    item list, which is more predictable for a JSON API than silently
    returning the last page.
    """
    total_pages = math.ceil(total / page_size) if total else 0
    offset = (page - 1) * page_size
    return offset, total_pages, page


def _paginate(items: list[Any], page: int, page_size: int) -> dict[str, Any]:
    """Slice a list into a standard pagination envelope."""
    total = len(items)
    offset, total_pages, effective_page = _page_bounds(total, page, page_size)
    return {
        "items": items[offset : offset + page_size],
        "total": total,
        "page": effective_page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


def _register_routes(app: FastAPI) -> None:
    """Attach every ``/api`` route to the application."""

    # -- health ------------------------------------------------------------ #

    @app.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["system"])
    def health(settings: SettingsDep, repository: RepositoryDep) -> HealthResponse:
        """Report application health, including whether the data source works.

        Returns ``200`` with ``status="ok"`` when data loads, and ``200`` with
        ``status="degraded"`` when the configured source is misconfigured or
        unreachable, so monitoring can distinguish the two without failing the
        request.  Credentials and file paths are never included.
        """
        checks: dict[str, Any] = {
            "data_source": settings.data_source,
            "applications_tab": settings.applications_tab if not settings.uses_csv else None,
            "job_openings_tab": settings.job_openings_tab if not settings.uses_csv else None,
            "google_sheets_configured": settings.google_sheets_configured()
            if not settings.uses_csv
            else None,
        }

        overall = "ok"
        try:
            dataset = repository.get_dataset()
        except DataSourceError as exc:
            logger.warning("Health check could not load data: %s", exc)
            overall = "degraded"
            checks["data_error"] = str(exc)
            checks["applications_rows"] = None
            checks["applications_unique"] = None
            checks["job_openings_rows"] = None
            checks["job_openings_unique"] = None
        else:
            checks["applications_rows"] = dataset.applications_rows
            checks["applications_unique"] = len(ana.build_application_records(dataset.applications))
            checks["job_openings_rows"] = dataset.job_openings_rows
            checks["job_openings_unique"] = len(ana.build_job_records(dataset.job_openings))
            checks["fetched_at"] = dataset.fetched_at.isoformat()
            checks["cached"] = dataset.cached

        return HealthResponse(
            status=overall,  # type: ignore[arg-type]
            app=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
            data_source=settings.data_source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            checks=checks,
        )

    # -- dashboard --------------------------------------------------------- #

    @app.get(f"{API_PREFIX}/dashboard", response_model=DashboardResponse, tags=["dashboard"])
    def dashboard(dataset: DatasetDep) -> DashboardResponse:
        """Return the Dashboard page payload in a single request."""
        summary = ana.build_dashboard(dataset, recent_limit=5, match_limit=5)
        return DashboardResponse(
            applications=ApplicationAnalytics(**summary.applications),
            jobs=JobAnalytics(**summary.jobs),
            top_matches=summary.top_matches,
            source=summary.source,
            data_freshness=summary.data_freshness,
            cached=summary.cached,
            fetched_at=summary.fetched_at.isoformat() if summary.fetched_at else None,
        )

    # -- applications ------------------------------------------------------ #

    @app.get(
        f"{API_PREFIX}/applications",
        response_model=ApplicationListResponse,
        tags=["applications"],
    )
    def list_applications(
        dataset: DatasetDep,
        settings: SettingsDep,
        status_filter: Annotated[
            str | None,
            Query(alias="status", max_length=MAX_FILTER_LENGTH),
        ] = None,
        platform: Annotated[
            str | None, Query(max_length=MAX_FILTER_LENGTH)
        ] = None,
        company: Annotated[
            str | None, Query(max_length=MAX_FILTER_LENGTH)
        ] = None,
        page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
        page_size: Annotated[int | None, Query(ge=1, description="Items per page.")] = None,
    ) -> ApplicationListResponse:
        """List tracked applications with optional filters and pagination.

        Filters are case-insensitive *substring* matches on the raw status or
        platform text, so ``?status=rejected`` finds ``Not Shortlisted /
        Rejected``.  Use ``category`` to filter by the derived category.
        """
        records = ana.build_application_records(dataset.applications)

        available_statuses = sorted({r["status"] for r in records if r["status"]})
        available_platforms = sorted({r["platform"] for r in records if r["platform"]})

        status_filter = _clean_filter(status_filter)
        platform = _clean_filter(platform)
        company = _clean_filter(company)

        if status_filter:
            needle = status_filter.casefold()
            records = [
                r
                for r in records
                if (r["status"] and needle in r["status"].casefold())
                or needle == r["status_category"]
            ]
        if platform:
            needle = platform.casefold()
            records = [
                r for r in records if r["platform"] and needle in r["platform"].casefold()
            ]
        if company:
            needle = company.casefold()
            records = [r for r in records if r["company"] and needle in r["company"].casefold()]

        size = _resolve_page_size(page_size, settings)
        envelope = _paginate(records, page, size)

        return ApplicationListResponse(
            items=[ApplicationRecord(**item) for item in envelope["items"]],
            total=envelope["total"],
            page=envelope["page"],
            page_size=envelope["page_size"],
            total_pages=envelope["total_pages"],
            available_statuses=available_statuses,
            available_platforms=available_platforms,
        )

    # -- jobs -------------------------------------------------------------- #

    @app.get(f"{API_PREFIX}/jobs", response_model=JobListResponse, tags=["jobs"])
    def list_jobs(
        dataset: DatasetDep,
        settings: SettingsDep,
        location: Annotated[
            str | None, Query(max_length=MAX_FILTER_LENGTH)
        ] = None,
        skill: Annotated[str | None, Query(max_length=MAX_FILTER_LENGTH)] = None,
        verification: Annotated[
            str | None, Query(max_length=MAX_FILTER_LENGTH)
        ] = None,
        work_arrangement: Annotated[
            str | None, Query(max_length=MAX_FILTER_LENGTH)
        ] = None,
        min_match_score: Annotated[
            float | None, Query(ge=0, le=100, description="Minimum heuristic match score.")
        ] = None,
        page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
        page_size: Annotated[int | None, Query(ge=1, description="Items per page.")] = None,
    ) -> JobListResponse:
        """List discovered listings with optional filters and pagination.

        Returns an empty page (not an error) when there are no listings yet,
        which is the current state of the ``Job Openings`` tab.
        """
        records = ana.build_job_records(dataset.job_openings)

        available_locations = sorted({r["location"] for r in records if r["location"]})
        available_verifications = sorted(
            {r["verification_status"] for r in records if r["verification_status"]}
        )

        location = _clean_filter(location)
        skill = _clean_filter(skill)
        verification = _clean_filter(verification)
        work_arrangement = _clean_filter(work_arrangement)

        if location:
            needle = location.casefold()
            records = [r for r in records if r["location"] and needle in r["location"].casefold()]
        if work_arrangement:
            needle = work_arrangement.casefold()
            records = [
                r
                for r in records
                if r["work_arrangement"] and needle in r["work_arrangement"].casefold()
            ]
        if verification:
            # Verification status is a controlled vocabulary, so match it
            # exactly (case-insensitively) rather than as a substring --
            # otherwise "verified" would also match "unverified".
            needle = verification.casefold()
            records = [
                r
                for r in records
                if r["verification_status"] and r["verification_status"].casefold() == needle
            ]
        if skill:
            needle = skill.casefold()
            records = [
                r
                for r in records
                if any(needle in item.casefold() for item in r.get("skills") or [])
            ]
        if min_match_score is not None:
            # Score every listing directly (no limit) so the threshold is
            # applied to the full set before pagination.
            scores = {
                record["id"]: float(ana.score_job_match(record)["score"])
                for record in records
            }
            records = [
                r for r in records if scores.get(r["id"], 0.0) >= min_match_score
            ]

        size = _resolve_page_size(page_size, settings)
        envelope = _paginate(records, page, size)

        return JobListResponse(
            items=[JobRecord(**item) for item in envelope["items"]],
            total=envelope["total"],
            page=envelope["page"],
            page_size=envelope["page_size"],
            total_pages=envelope["total_pages"],
            available_locations=available_locations,
            available_verification_statuses=available_verifications,
        )

    # -- analytics: applications ------------------------------------------- #

    @app.get(
        f"{API_PREFIX}/analytics/applications",
        response_model=ApplicationAnalytics,
        tags=["analytics"],
    )
    def analytics_applications(dataset: DatasetDep) -> ApplicationAnalytics:
        """Return status distribution and monthly application trends."""
        return ApplicationAnalytics(
            **ana.application_analytics(dataset.applications, recent_limit=5)
        )

    # -- analytics: jobs --------------------------------------------------- #

    @app.get(f"{API_PREFIX}/analytics/jobs", response_model=JobAnalytics, tags=["analytics"])
    def analytics_jobs(dataset: DatasetDep) -> JobAnalytics:
        """Return job-market analytics (safe when there are zero listings)."""
        return JobAnalytics(**ana.job_analytics(dataset.job_openings))

    # -- analytics: skills ------------------------------------------------- #

    @app.get(
        f"{API_PREFIX}/analytics/skills", response_model=SkillAnalytics, tags=["analytics"]
    )
    def analytics_skills(
        dataset: DatasetDep,
        limit: Annotated[int, Query(ge=1, le=100, description="Max skills to return.")] = 20,
        min_count: Annotated[
            int, Query(ge=1, description="Only skills requested by at least N listings.")
        ] = 1,
    ) -> SkillAnalytics:
        """Return the most frequently requested skills across listings."""
        records = ana.build_job_records(dataset.job_openings)
        skills = ana.top_skills(dataset.job_openings, limit=limit, min_count=min_count)
        total_mentions = sum(row["count"] for row in skills)
        return SkillAnalytics(
            total_listings=len(records),
            total_skill_mentions=total_mentions,
            unique_skills=len({row["skill"] for row in skills}),
            skills=skills,
            min_count=min_count,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # -- analytics: matching ----------------------------------------------- #

    @app.get(
        f"{API_PREFIX}/analytics/matching", response_model=MatchingResponse, tags=["analytics"]
    )
    def analytics_matching(
        dataset: DatasetDep,
        limit: Annotated[int, Query(ge=1, le=MAX_RECOMMENDED_MATCHES)] = 20,
        min_score: Annotated[float, Query(ge=0, le=100)] = 0.0,
        include_unmatched: Annotated[
            bool, Query(description="Also return listings with a zero score.")
        ] = False,
    ) -> MatchingResponse:
        """Return explainable matches between listings and my preferences.

        This is a transparent keyword heuristic, not an AI prediction.  Each
        match carries the reasons behind its score.
        """
        records = ana.build_job_records(dataset.job_openings)
        matches = ana.match_jobs(
            dataset.job_openings,
            limit=limit,
            min_score=min_score,
            include_unmatched=include_unmatched,
        )
        return MatchingResponse(
            matches=matches,
            total_listings=len(records),
            matched_listings=len([m for m in matches if m["score"] > 0]),
            min_score=min_score,
            include_unmatched=include_unmatched,
            interests=sorted(ana.INTEREST_KEYWORDS),
            preferred_locations=sorted(ana.PREFERRED_LOCATIONS),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # -- meta -------------------------------------------------------------- #

    @app.get(f"{API_PREFIX}/meta", tags=["system"])
    def meta() -> dict[str, Any]:
        """Describe the active configuration (no secrets, no file paths)."""
        active = app.state.settings
        return {
            "app": active.app_name,
            "version": active.app_version,
            "environment": active.environment,
            "data_source": active.data_source,
            "applications_tab": active.applications_tab,
            "job_openings_tab": active.job_openings_tab,
            "cache_ttl_seconds": active.sheets_cache_ttl_seconds,
            "status_categories": list(ana.CATEGORY_ORDER),
            "interests": sorted(ana.INTEREST_KEYWORDS),
            "preferred_locations": sorted(ana.PREFERRED_LOCATIONS),
        }


def _resolve_page_size(page_size: int | None, settings: Settings) -> int:
    """Clamp a requested page size into the configured bounds."""
    if page_size is None:
        return settings.default_page_size
    return max(1, min(page_size, settings.max_page_size))


# Re-create the module-level app so ``uvicorn app.main:app`` works.
app = create_app()


__all__ = ["app", "create_app", "get_dataset", "get_repository", "get_settings"]