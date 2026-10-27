"""Application configuration loaded from environment variables.

All settings are read once at import time from the process environment, with
``.env`` (in ``backend/``) loaded as a fallback.  Nothing here contains a real
credential: values come from the environment or from safe defaults.

Precedence, highest first:

1. Real environment variables (set by the shell / CI / hosting platform).
2. ``backend/.env`` (loaded by ``python-dotenv``).
3. The defaults declared in this module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# ``backend/`` is the parent of ``backend/app/``.
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Load ``backend/.env`` if it exists.  ``override=False`` keeps real env vars
# authoritative, which is what we want in Docker/CI.
load_dotenv(BACKEND_DIR / ".env", override=False)

DataSource = Literal["csv", "google_sheets"]

#: Default development origin for the React/Vite frontend.
DEFAULT_DEV_ORIGIN = "http://localhost:3000"


def _env(name: str, default: str = "") -> str:
    """Read a stripped environment variable, falling back to ``default``."""
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, ignoring unparseable values."""
    raw = _env(name)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable.

    Accepts ``1/true/yes/on`` and ``0/false/no/off`` (case-insensitive).
    """
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path | None) -> Path | None:
    """Resolve a filesystem path from the environment.

    Relative paths are resolved against ``backend/`` so that the app behaves the
    same regardless of the directory uvicorn was launched from.
    """
    raw = _env(name)
    if not raw:
        return default
    candidate = Path(os.path.expandvars(raw)).expanduser()
    if not candidate.is_absolute():
        candidate = BACKEND_DIR / candidate
    return candidate


def _env_list(name: str, default: list[str]) -> list[str]:
    """Read a comma-separated environment variable into a list."""
    raw = _env(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration.

    Attributes:
        data_source: ``"csv"`` or ``"google_sheets"``.
        data_dir: Directory holding ``applications.csv`` and ``job_openings.csv``
            when ``data_source`` is ``"csv"``.
        applications_csv / job_openings_csv: Concrete CSV paths.
        spreadsheet_id: Google Sheets spreadsheet ID (no ``/edit`` suffix).
        google_credentials_path: Path to the service-account JSON key file.
        applications_tab / job_openings_tab: Tab (worksheet) names.  The real
            spreadsheet may still be called ``Sheet1``; this stays configurable
            so the tab is never renamed.
        sheets_cache_ttl_seconds: How long a Sheets read is reused before a
            fresh fetch.  ``0`` disables caching entirely.
        sheets_read_retry_attempts: Number of read attempts on transient errors.
        cors_origins: Origins allowed by CORS middleware.
    """

    # --- general -----------------------------------------------------------
    app_name: str = "JobPilot API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # --- data source -------------------------------------------------------
    data_source: DataSource = "csv"
    data_dir: Path = BACKEND_DIR / "data"
    applications_csv: Path = BACKEND_DIR / "data" / "applications.csv"
    job_openings_csv: Path = BACKEND_DIR / "data" / "job_openings.csv"

    # --- google sheets (read-only) ----------------------------------------
    spreadsheet_id: str = ""
    google_credentials_path: Path | None = None
    applications_tab: str = "Applications"
    job_openings_tab: str = "Job Openings"
    sheets_cache_ttl_seconds: int = 300
    sheets_read_retry_attempts: int = 2

    # --- http --------------------------------------------------------------
    cors_origins: list[str] = field(default_factory=lambda: [DEFAULT_DEV_ORIGIN])

    # --- pagination defaults ----------------------------------------------
    default_page_size: int = 50
    max_page_size: int = 200

    @property
    def uses_csv(self) -> bool:
        """True when CSV files are the active data source."""
        return self.data_source == "csv"

    def google_sheets_configured(self) -> bool:
        """True when both a spreadsheet ID and a credentials file are present."""
        if not self.spreadsheet_id:
            return False
        return self.google_credentials_path is not None


def _normalise_data_source(raw: str) -> DataSource:
    """Map a ``DATA_SOURCE`` string onto a supported value.

    Unknown values fall back to ``"csv"`` so a typo can never stop the app from
    booting in local mode.
    """
    value = raw.strip().lower().replace("-", "_")
    if value == "google_sheets":
        return "google_sheets"
    return "csv"


def load_settings() -> Settings:
    """Build a :class:`Settings` instance from the current environment."""
    data_dir = _env_path("DATA_DIR", BACKEND_DIR / "data") or BACKEND_DIR / "data"
    credentials = _env_path("GOOGLE_APPLICATION_CREDENTIALS", None)

    ttl = max(0, _env_int("SHEETS_CACHE_TTL_SECONDS", 300))
    attempts = max(1, _env_int("SHEETS_READ_RETRY_ATTEMPTS", 2))
    page_size = max(1, _env_int("DEFAULT_PAGE_SIZE", 50))
    max_page = max(page_size, _env_int("MAX_PAGE_SIZE", 200))

    return Settings(
        app_name=_env("APP_NAME", "JobPilot API"),
        app_version=_env("APP_VERSION", "0.1.0"),
        environment=_env("ENVIRONMENT", "development"),
        data_source=_normalise_data_source(_env("DATA_SOURCE", "csv")),
        data_dir=data_dir,
        applications_csv=data_dir / "applications.csv",
        job_openings_csv=data_dir / "job_openings.csv",
        spreadsheet_id=_env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        google_credentials_path=credentials,
        applications_tab=_env("GOOGLE_SHEETS_APPLICATIONS_TAB", "Applications"),
        job_openings_tab=_env("GOOGLE_SHEETS_JOBS_TAB", "Job Openings"),
        sheets_cache_ttl_seconds=ttl,
        sheets_read_retry_attempts=attempts,
        cors_origins=_env_list("CORS_ORIGINS", [DEFAULT_DEV_ORIGIN]),
        default_page_size=page_size,
        max_page_size=max_page,
    )


settings = load_settings()


def reload_settings() -> Settings:
    """Re-read the environment and replace the cached settings object.

    Used by tests so they can point the app at temporary fixtures.
    """
    global settings
    settings = load_settings()
    return settings


__all__ = [
    "BACKEND_DIR",
    "DEFAULT_DEV_ORIGIN",
    "Settings",
    "load_settings",
    "reload_settings",
    "settings",
]