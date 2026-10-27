"""Read-only data sources for JobPilot.

This module is the only place that touches either the CSV exports or the Google
Sheets API.  It exposes a single function, :func:`load_dataset`, which returns a
:class:`Dataset` of two normalised :class:`pandas.DataFrame` objects.

Design rules enforced here:

* **Read-only.**  Nothing in this module can write, append, update or delete a
  spreadsheet record.
* **Never invent data.**  An empty ``Job Openings`` tab yields an empty frame.
* **No credentials in responses.**  Errors are converted into typed exceptions
  with safe, user-facing messages; credential paths never leave the backend.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import pandas as pd

from .config import Settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class DataSourceError(RuntimeError):
    """Base class for data-source problems safe to surface to API clients."""


class DataFileNotFoundError(DataSourceError):
    """A configured CSV file does not exist."""


class DataFileUnreadableError(DataSourceError):
    """A configured CSV file exists but could not be parsed."""


class GoogleSheetsAuthError(DataSourceError):
    """Google Sheets rejected the service-account credentials or permissions."""


class GoogleSheetsQuotaError(DataSourceError):
    """Google Sheets rate limit / quota was hit."""


class GoogleSheetsUnavailableError(DataSourceError):
    """Google Sheets was unreachable, or the spreadsheet/tab is missing."""


class GoogleSheetsNotConfiguredError(DataSourceError):
    """``DATA_SOURCE=google_sheets`` but the required settings are missing."""


# --------------------------------------------------------------------------- #
# Column normalisation
# --------------------------------------------------------------------------- #

#: Tokens that mean "this cell has no value".
MISSING_TOKENS = frozenset({"", "-", "--", "n/a", "na", "n.a.", "nan", "none", "null", "nil"})

#: Canonical column names for the *Applications* tab.
#: Keys are the normalised header slugs produced by :func:`normalise_header`
#: (lowercase, underscores), e.g. ``"Role/Position"`` -> ``"role_position"``.
APPLICATION_COLUMN_ALIASES: dict[str, str] = {
    "company_name": "company",
    "company": "company",
    "organisation": "company",
    "organization": "company",
    "role_position": "role",
    "role": "role",
    "position": "role",
    "application_type": "application_type",
    "application_date": "application_date",
    "applied_date": "application_date",
    "date_applied": "application_date",
    "latest_update_date": "latest_update_date",
    "last_update_date": "latest_update_date",
    "updated_date": "latest_update_date",
    "current_status": "status",
    "status": "status",
    "job_id_req_id": "job_id",
    "job_id": "job_id",
    "req_id": "job_id",
    "requisition_id": "job_id",
    "platform_portal": "platform",
    "platform": "platform",
    "portal": "platform",
    "notes_next_action_items": "notes",
    "notes": "notes",
    "next_action_items": "notes",
    "next_actions": "notes",
    "tracking_key": "tracking_key",
}

#: Canonical column names for the *Job Openings* tab.
JOB_COLUMN_ALIASES: dict[str, str] = {
    "company": "company",
    "organisation": "company",
    "organization": "company",
    "internship_title": "title",
    "job_title": "title",
    "title": "title",
    "role": "title",
    "location": "location",
    "work_arrangement": "work_arrangement",
    "work_mode": "work_arrangement",
    "work_type": "work_arrangement",
    "start_date": "start_date",
    "duration": "duration",
    "stipend": "stipend",
    "salary": "stipend",
    "ctc": "stipend",
    "eligibility": "eligibility",
    "application_deadline": "application_deadline",
    "deadline": "application_deadline",
    "required_skills": "required_skills",
    "skills": "required_skills",
    "tech_stack": "required_skills",
    "fit_assessment": "fit_assessment",
    "verification_status": "verification_status",
    "verified": "verification_status",
    "application_url": "application_url",
    "apply_url": "application_url",
    "job_url": "application_url",
    "source_url": "source_url",
    "date_found": "date_found",
    "unique_job_key": "unique_job_key",
}

#: Columns that are parsed as timestamps, per dataset.
APPLICATION_DATE_COLUMNS = ("application_date", "latest_update_date")
JOB_DATE_COLUMNS = ("start_date", "application_deadline", "date_found")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalise_header(raw: Any) -> str:
    """Turn a raw spreadsheet header cell into a snake_case slug.

    ``"Role/Position"`` becomes ``"role_position"``, ``" Platform/Portal "``
    becomes ``"platform_portal"``.  Empty cells become an empty string.

    Args:
        raw: The header cell as read from CSV or Sheets.

    Returns:
        A lowercase, underscore-separated slug.
    """
    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        return ""
    text = _SLUG_RE.sub("_", str(raw).strip().lower()).strip("_")
    return text


def is_missing(value: Any) -> bool:
    """Return ``True`` when a cell should be treated as "no data".

    Blank strings, ``pandas`` nulls, and placeholder text such as ``"N/A"``,
    ``"None"`` and ``"-"`` all count as missing.  This is why the analytics
    layer can report an honest "missing data" count.
    """
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if not isinstance(value, str):
        # pd.NA / numpy nan
        try:
            if pd.isna(value):
                return True
        except (TypeError, ValueError):
            return False
        return False
    return value.strip().lower() in MISSING_TOKENS


def _slug_to_series(values: Iterable[Any]) -> pd.Series:
    """Apply :func:`normalise_header` element-wise to a header row."""
    return pd.Series(list(values), dtype="object").map(
        lambda value: normalise_header(value) if not is_missing(value) else ""
    )


def _detect_header_row(raw: pd.DataFrame, min_header_cells: int = 3) -> int:
    """Find the row index that holds the real header.

    A Google Sheets export can contain a title block and summary statistics
    above the actual header (``applications.csv`` has its header on row 7).
    The first row is treated as the header when it looks like one:

    * at least ``min_header_cells`` non-empty cells, and
    * no cell that looks like a number or a date (summary rows are full of
      them).

    Because the sheet is read with ``dtype=str``, "numbers" are matched as text
    patterns rather than as Python numeric types.

    Args:
        raw: The whole sheet loaded with ``header=None``.
        min_header_cells: Minimum number of non-empty cells for a header row.

    Returns:
        Zero-based row index of the header, or ``0`` when nothing matches.
    """
    date_like = re.compile(r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*$")
    numeric_like = re.compile(r"^[+-]?[\d,]*\.?\d+\s*%?$")

    def looks_like_value(cell: Any) -> bool:
        """True when a cell is a date or a number, i.e. not a header label."""
        if isinstance(cell, (int, float)) and not isinstance(cell, bool):
            return True
        if isinstance(cell, str):
            text = cell.strip()
            return bool(date_like.match(text) or numeric_like.match(text))
        return False

    for index in range(len(raw)):
        row = raw.iloc[index]
        cells = [cell for cell in row.tolist() if not is_missing(cell)]
        if len(cells) < min_header_cells:
            continue
        if any(looks_like_value(cell) for cell in cells):
            continue
        return index

    return 0


def _drop_spare_label_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove spreadsheet row-label columns that carry no information.

    A CSV export of Sheets often starts with an unnamed, entirely empty column
    (the spreadsheet's row-number gutter).  It is dropped here.  Columns that
    are unnamed but actually hold values are kept and given an
    ``unnamed_<n>`` name so no data is lost.
    """
    drop: list[str] = []
    for position, column in enumerate(frame.columns):
        header = normalise_header(column)
        if header:
            continue
        series = frame[column]
        # ``is_missing`` maps placeholder text to missing as well, which is what
        # we want here: an unnamed column of "N/A" cells carries nothing.
        if series.map(is_missing).all():
            drop.append(column)
            continue
        frame = frame.rename(columns={column: f"unnamed_{position}"})

    return frame.drop(columns=drop) if drop else frame


def _rename_to_canonical(frame: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    """Rename header slugs to canonical names, keeping unknown columns intact."""
    renamed = {}
    for column in frame.columns:
        slug = normalise_header(column)
        renamed[column] = aliases.get(slug, slug or f"column_{len(renamed)}")
    return frame.rename(columns=renamed)


def _dedupe_column_names(frame: pd.DataFrame) -> pd.DataFrame:
    """Make column labels unique by appending ``_2``, ``_3`` ... on collision."""
    seen: dict[str, int] = {}
    final: dict[Any, str] = {}
    for column in frame.columns:
        base = str(column)
        if base in seen:
            seen[base] += 1
            final[column] = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
            final[column] = base
    return frame.rename(columns=final)


def _parse_dates(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Best-effort parse of date columns into tz-naive ISO timestamps.

    Unparseable cells become ``NaT`` instead of raising, and the column stays in
    the frame so the analytics layer can report missing data.
    """
    frame = frame.copy()
    for column in columns:
        if column not in frame.columns:
            continue
        text = frame[column].astype("string").str.strip()
        cleaned = text.mask(text.map(is_missing))
        try:
            frame[column] = pd.to_datetime(cleaned, errors="coerce", format="mixed")
        except (ValueError, TypeError):  # pragma: no cover - older pandas
            frame[column] = pd.to_datetime(cleaned, errors="coerce")
    return frame


def _clean_strings(frame: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace and convert missing placeholders to ``pandas`` nulls."""
    frame = frame.copy()
    for column in frame.columns:
        series = frame[column].astype("object")
        trimmed = series.map(lambda v: v.strip() if isinstance(v, str) else v)
        frame[column] = trimmed.mask(trimmed.map(is_missing), other=None)
    return frame


def normalise_frame(
    raw: pd.DataFrame,
    aliases: dict[str, str],
    date_columns: Sequence[str],
) -> pd.DataFrame:
    """Turn a raw sheet (possibly with a title block) into a clean DataFrame.

    Args:
        raw: Whole sheet loaded with ``header=None``, everything as strings.
        aliases: Header slug -> canonical column name mapping.
        date_columns: Columns to parse as dates.

    Returns:
        A DataFrame with normalised column names, trimmed strings, real nulls
        and parsed date columns.  Empty sheets return an empty DataFrame.
    """
    if raw.empty:
        return pd.DataFrame()

    header_index = _detect_header_row(raw)
    header = _slug_to_series(raw.iloc[header_index].tolist())
    body = raw.iloc[header_index + 1 :].reset_index(drop=True)
    body.columns = header

    body = body.loc[:, [bool(name) for name in header]]
    body = _drop_spare_label_columns(body)
    body = _rename_to_canonical(body, aliases)
    body = _dedupe_column_names(body)
    body = _clean_strings(body)

    # A summary/statistics row can survive header detection; drop rows with no
    # content at all so they cannot be counted as applications.
    if not body.empty:
        content_mask = ~body.apply(
            lambda row: all(value is None or pd.isna(value) for value in row), axis=1
        )
        body = body.loc[content_mask].reset_index(drop=True)

    return _parse_dates(body, date_columns)


# --------------------------------------------------------------------------- #
# CSV reading
# --------------------------------------------------------------------------- #


def read_csv_sheet(path: Path, aliases: dict[str, str], date_columns: Sequence[str]) -> pd.DataFrame:
    """Read and normalise one CSV export.

    Args:
        path: Path to the CSV file.
        aliases: Header slug -> canonical column mapping.
        date_columns: Columns to parse as dates.

    Returns:
        A normalised DataFrame.  A header-only file yields an empty DataFrame.

    Raises:
        DataFileNotFoundError: The file does not exist.
        DataFileUnreadableError: The file could not be parsed as CSV.
    """
    path = Path(path)
    if not path.is_file():
        raise DataFileNotFoundError(f"Data file not found: {path.name}")

    try:
        raw = pd.read_csv(
            path,
            dtype=str,
            header=None,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=True,
            encoding="utf-8-sig",
        )
    except (pd.errors.ParserError, UnicodeDecodeError, OSError) as exc:
        raise DataFileUnreadableError(f"Could not parse {path.name}: {exc}") from exc

    return normalise_frame(raw, aliases, date_columns)


def sheet_values_to_frame(values: Sequence[Sequence[Any]]) -> pd.DataFrame:
    """Convert a Google Sheets ``get_all_values()`` result into a raw frame."""
    if not values:
        return pd.DataFrame()
    width = max(len(row) for row in values)
    padded = [list(row) + [None] * (width - len(row)) for row in values]
    return pd.DataFrame(padded, dtype="object")


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #


@dataclass
class _CacheEntry:
    """A cached dataset plus its expiry timestamp."""

    dataset: "Dataset"
    expires_at: float


class TTLCache:
    """A very small thread-safe time-to-live cache.

    Used so a burst of dashboard requests does not hit the Sheets API quota.
    ``ttl_seconds <= 0`` disables caching entirely.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = max(0, int(ttl_seconds))
        self._entry: _CacheEntry | None = None
        self._lock = threading.Lock()

    def get(self) -> "Dataset | None":
        """Return the cached dataset when present and still fresh."""
        if self.ttl_seconds <= 0:
            return None
        with self._lock:
            if self._entry is None:
                return None
            if time.monotonic() >= self._entry.expires_at:
                return None
            return self._entry.dataset

    def set(self, dataset: "Dataset") -> None:
        """Store a dataset for ``ttl_seconds``."""
        if self.ttl_seconds <= 0:
            return
        with self._lock:
            self._entry = _CacheEntry(dataset, time.monotonic() + self.ttl_seconds)

    def invalidate(self) -> None:
        """Drop any cached dataset, forcing the next read to hit the source."""
        with self._lock:
            self._entry = None


# --------------------------------------------------------------------------- #
# Google Sheets client (read-only)
# --------------------------------------------------------------------------- #


#: OAuth scopes requested for the service account.
#:
#: ``gspread`` has no per-call read-only flag -- ``Client.open_by_key()`` takes
#: only the spreadsheet ID -- so read-only access is enforced at the *OAuth*
#: layer instead.  The service account is granted nothing but the read-only
#: Sheets scope, which means its access token cannot perform a write, append,
#: update, delete or rename even if such a call were ever added by mistake.
#:
#: This is deliberately narrower than ``gspread.auth.READONLY_SCOPES``, which
#: also requests ``drive.readonly``.  This backend resolves the spreadsheet with
#: ``open_by_key()`` (a plain ``spreadsheets.get``), so the Drive scope is not
#: needed and is not asked for.
GOOGLE_SHEETS_READONLY_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/spreadsheets.readonly",
)


class GoogleSheetsReader:
    """Minimal read-only Google Sheets client built on ``gspread``.

    Read-only access comes from the OAuth scope, not from a method argument:
    the spreadsheet is opened with ``Client.open_by_key(spreadsheet_id)`` using
    credentials restricted to :data:`GOOGLE_SHEETS_READONLY_SCOPES`.  The only
    Sheets call this class makes is ``worksheet.get_all_values()``, so no code
    path here can modify the spreadsheet.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _ensure_configured(self) -> None:
        """Validate that Sheets mode has everything it needs."""
        if not self._settings.spreadsheet_id:
            raise GoogleSheetsNotConfiguredError(
                "GOOGLE_SHEETS_SPREADSHEET_ID is not set."
            )
        if self._settings.google_credentials_path is None:
            raise GoogleSheetsNotConfiguredError(
                "GOOGLE_APPLICATION_CREDENTIALS is not set."
            )
        if not self._settings.google_credentials_path.is_file():
            raise GoogleSheetsNotConfiguredError(
                "The Google credentials file configured by "
                "GOOGLE_APPLICATION_CREDENTIALS does not exist."
            )

    def _get_client(self) -> Any:
        """Return an authorised gspread client, creating it on first use."""
        if self._client is not None:
            return self._client

        self._ensure_configured()
        try:
            import gspread  # imported lazily so CSV mode has no hard dependency
            from google.oauth2.service_account import Credentials
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise GoogleSheetsUnavailableError(
                "Google Sheets support requires 'gspread' and 'google-auth'."
            ) from exc

        credentials_path = self._settings.google_credentials_path
        assert credentials_path is not None  # narrowed by _ensure_configured

        try:
            credentials = Credentials.from_service_account_file(
                str(credentials_path), scopes=list(GOOGLE_SHEETS_READONLY_SCOPES)
            )
            self._client = gspread.authorize(credentials)
        except Exception as exc:  # noqa: BLE001 - gspread raises many types
            raise GoogleSheetsAuthError(
                f"Could not authenticate with Google Sheets: {exc}"
            ) from exc

        return self._client

    def _open_workbook(self) -> Any:
        """Open the configured spreadsheet.

        ``gspread.Client.open_by_key`` takes only the spreadsheet ID -- it has no
        ``readonly`` parameter.  Access is already limited to the read-only
        Sheets scope by :meth:`_get_client`.
        """
        client = self._get_client()
        try:
            return client.open_by_key(self._settings.spreadsheet_id)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc

    @staticmethod
    def _translate_error(exc: Exception) -> DataSourceError:
        """Map a Google API exception onto a safe, typed backend error."""
        text = f"{type(exc).__name__}: {exc}".lower()
        if "quota" in text or "ratelimit" in text or "rate limit" in text or "403" in text:
            return GoogleSheetsQuotaError("Google Sheets quota or rate limit reached.")
        if (
            "permission" in text
            or "unauthorized" in text
            or "unauthenticated" in text
            or "credentials" in text
            or "401" in text
        ):
            return GoogleSheetsAuthError(
                "Google Sheets rejected the credentials. Check the service account "
                "e-mail has read access to the spreadsheet."
            )
        if "not found" in text or "nosuch" in text or "404" in text:
            return GoogleSheetsUnavailableError(
                "The spreadsheet or tab was not found. Check GOOGLE_SHEETS_* settings."
            )
        return GoogleSheetsUnavailableError(f"Google Sheets request failed: {exc}")

    def read_tab(self, tab_name: str) -> pd.DataFrame:
        """Return the raw cell values of one tab.

        A missing or empty tab returns an empty DataFrame rather than raising,
        so an unpopulated ``Job Openings`` tab cannot break the API.

        Args:
            tab_name: Exact worksheet name, for example ``"Sheet1"``.

        Returns:
            A DataFrame of raw string cells with no header applied.
        """
        self._ensure_configured()
        last_error: DataSourceError | None = None

        for attempt in range(1, self._settings.sheets_read_retry_attempts + 1):
            try:
                workbook = self._open_workbook()
                try:
                    worksheet = workbook.worksheet(tab_name)
                except Exception as exc:  # noqa: BLE001
                    # gspread.WorksheetNotFound and friends.
                    raise GoogleSheetsUnavailableError(
                        f"Tab '{tab_name}' was not found. Set the matching "
                        "GOOGLE_SHEETS_*_TAB variable to the real tab name."
                    ) from exc

                values = worksheet.get_all_values()
                return sheet_values_to_frame(values)
            except DataSourceError as exc:
                last_error = exc
                # Retry transient problems; never retry configuration errors.
                retryable = isinstance(
                    exc, (GoogleSheetsQuotaError, GoogleSheetsUnavailableError)
                )
                if not retryable or attempt >= self._settings.sheets_read_retry_attempts:
                    break
                time.sleep(min(2**attempt, 8))
            except Exception as exc:  # noqa: BLE001
                last_error = self._translate_error(exc)
                break

        assert last_error is not None
        raise last_error


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Dataset:
    """A consistent snapshot of both tabs.

    Attributes:
        applications: Normalised applications DataFrame.
        job_openings: Normalised job listings DataFrame.
        source: ``"csv"`` or ``"google_sheets"``.
        fetched_at: Timezone-aware UTC timestamp of when this snapshot was read.
        applications_rows / job_openings_rows: Row counts, for quick health info.
        cached: Whether the snapshot was served from cache.
    """

    applications: pd.DataFrame
    job_openings: pd.DataFrame
    source: str
    fetched_at: datetime
    applications_rows: int = field(default=0)
    job_openings_rows: int = field(default=0)
    cached: bool = False

    def with_cached_flag(self, cached: bool) -> "Dataset":
        """Return a copy of this dataset with the ``cached`` flag updated."""
        return Dataset(
            applications=self.applications,
            job_openings=self.job_openings,
            source=self.source,
            fetched_at=self.fetched_at,
            applications_rows=self.applications_rows,
            job_openings_rows=self.job_openings_rows,
            cached=cached,
        )


def _load_applications_csv(path: Path) -> pd.DataFrame:
    """Load and normalise ``applications.csv``."""
    return read_csv_sheet(path, APPLICATION_COLUMN_ALIASES, APPLICATION_DATE_COLUMNS)


def _load_jobs_csv(path: Path) -> pd.DataFrame:
    """Load and normalise ``job_openings.csv`` (header-only files are fine)."""
    return read_csv_sheet(path, JOB_COLUMN_ALIASES, JOB_DATE_COLUMNS)


class DataRepository:
    """Loads the dataset from whichever source the settings select.

    CSV mode reads the local exports on every request (cheap, and keeps local
    iteration simple).  Google Sheets mode serves a short TTL cache so a page
    load does not burn API quota; call :meth:`invalidate` to force a refresh.
    """

    def __init__(
        self,
        settings: Settings,
        reader: GoogleSheetsReader | None = None,
        cache: TTLCache | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.reader = reader
        self.cache = cache if cache is not None else TTLCache(settings.sheets_cache_ttl_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- public API -------------------------------------------------------- #

    def get_dataset(self, *, refresh: bool = False) -> Dataset:
        """Return the current dataset, using the cache when it is still fresh.

        Args:
            refresh: Force a re-read, bypassing (and invalidating) the cache.

        Returns:
            A :class:`Dataset`.

        Raises:
            DataFileNotFoundError: CSV mode and a file is missing.
            DataSourceError: Sheets mode failed (auth, quota, missing tab).
        """
        if self.settings.uses_csv:
            return self._load_from_csv()

        if refresh:
            self.cache.invalidate()

        cached = self.cache.get()
        if cached is not None:
            return cached.with_cached_flag(True)

        dataset = self._load_from_sheets()
        self.cache.set(dataset)
        return dataset

    def invalidate_cache(self) -> None:
        """Drop cached Sheets data so the next read hits Google."""
        self.cache.invalidate()

    # -- backends ---------------------------------------------------------- #

    def _load_from_csv(self) -> Dataset:
        """Read both CSV files and build a :class:`Dataset`."""
        applications = _load_applications_csv(self.settings.applications_csv)
        job_openings = _load_jobs_csv(self.settings.job_openings_csv)
        return Dataset(
            applications=applications,
            job_openings=job_openings,
            source="csv",
            fetched_at=self._clock(),
            applications_rows=len(applications),
            job_openings_rows=len(job_openings),
            cached=False,
        )

    def _load_from_sheets(self) -> Dataset:
        """Read both tabs from Google Sheets and build a :class:`Dataset`."""
        if self.reader is None:
            self.reader = GoogleSheetsReader(self.settings)

        applications_raw = self.reader.read_tab(self.settings.applications_tab)
        jobs_raw = self.reader.read_tab(self.settings.job_openings_tab)

        applications = normalise_frame(
            applications_raw, APPLICATION_COLUMN_ALIASES, APPLICATION_DATE_COLUMNS
        )
        job_openings = normalise_frame(jobs_raw, JOB_COLUMN_ALIASES, JOB_DATE_COLUMNS)

        return Dataset(
            applications=applications,
            job_openings=job_openings,
            source="google_sheets",
            fetched_at=self._clock(),
            applications_rows=len(applications),
            job_openings_rows=len(job_openings),
            cached=False,
        )


__all__ = [
    "APPLICATION_COLUMN_ALIASES",
    "APPLICATION_DATE_COLUMNS",
    "DataFileNotFoundError",
    "DataFileUnreadableError",
    "DataRepository",
    "DataSourceError",
    "Dataset",
    "GoogleSheetsAuthError",
    "GoogleSheetsNotConfiguredError",
    "GoogleSheetsQuotaError",
    "GoogleSheetsReader",
    "GoogleSheetsUnavailableError",
    "GOOGLE_SHEETS_READONLY_SCOPES",
    "JOB_COLUMN_ALIASES",
    "JOB_DATE_COLUMNS",
    "TTLCache",
    "is_missing",
    "normalise_frame",
    "normalise_header",
    "read_csv_sheet",
]