"""Shared pytest fixtures.

Two fixture families are provided:

* **Synthetic fixtures** written from scratch in ``tmp_path``.  These cover the
  edge cases (empty job openings, missing values, unknown statuses, duplicate
  rows, odd dates) and contain no real personal data.
* **Real-data fixtures** that copy the project's own CSV exports into
  ``tmp_path`` and assert against their observed shape.  The originals are only
  ever read; the temporary copies are what the tests point the app at.
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analytics import build_application_records, build_job_records
from app.config import BACKEND_DIR, Settings
from app.main import create_app
from app.sheets import DataRepository

#: Deterministic clock for every test that would otherwise use ``now()``.
FIXED_NOW = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

#: The application's own CSV exports, used read-only by the "real data" tests.
REAL_DATA_DIR = BACKEND_DIR / "data"
REAL_APPLICATIONS_CSV = REAL_DATA_DIR / "applications.csv"
REAL_JOBS_CSV = REAL_DATA_DIR / "job_openings.csv"

#: The real Applications tab columns, in order.
SHEET_HEADER = [
    "Company Name",
    "Role/Position",
    "Application Type",
    "Application Date",
    "Latest Update Date",
    "Current Status",
    "Job ID/Req ID",
    "Platform/Portal",
    "Notes/Next Action Items",
    "Tracking Key",
]

#: The real Job Openings tab columns, in order.
JOB_HEADER = [
    "Company",
    "Internship Title",
    "Location",
    "Work Arrangement",
    "Start Date",
    "Duration",
    "Stipend",
    "Eligibility",
    "Application Deadline",
    "Required Skills",
    "Fit Assessment",
    "Verification Status",
    "Application URL",
    "Source URL",
    "Date Found",
    "Unique Job Key",
]


# --------------------------------------------------------------------------- #
# Raw CSV builders
# --------------------------------------------------------------------------- #

#: A real export has one empty gutter column in front of the real columns.
SHEET_WIDTH = len(SHEET_HEADER) + 1


def _row(values: list[str], width: int) -> list[str]:
    """Left-align a row and pad it with empty cells to ``width`` columns."""
    if len(values) > width:
        raise ValueError(f"Row has {len(values)} cells, expected at most {width}: {values!r}")
    return values + [""] * (width - len(values))


def _write_csv(path: Path, lines: list[list[str]]) -> Path:
    """Write pre-split rows to ``path``, letting ``csv`` handle quoting."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(lines)
    return path


def write_applications_csv(
    path: Path, rows: list[list[str]], *, with_preamble: bool = True
) -> Path:
    """Write an applications CSV, optionally with the real title-block preamble.

    Rows are lists of the ten real column values; the empty gutter column and
    the preamble are added automatically so the file matches a real Sheets
    export (header on row 7).
    """
    lines: list[list[str]] = []
    if with_preamble:
        blank = _row([], SHEET_WIDTH)
        lines += [
            blank,
            _row(["", "Job & Internship Application Tracker"], SHEET_WIDTH),
            blank,
            _row(
                [
                    "",
                    "Total Applications",
                    "25",
                    "Active Applications",
                    "15",
                    "Rejected",
                    "10",
                ],
                SHEET_WIDTH,
            ),
            blank,
            blank,
            _row([""] + SHEET_HEADER, SHEET_WIDTH),
        ]
    else:
        lines.append(_row([""] + SHEET_HEADER, SHEET_WIDTH))

    lines += [_row([""] + values, SHEET_WIDTH) for values in rows]
    return _write_csv(path, lines)


def write_jobs_csv(
    path: Path, rows: list[list[str]] | None = None, *, header_only: bool = False
) -> Path:
    """Write a job-openings CSV, optionally containing only the header row."""
    lines: list[list[str]] = [list(JOB_HEADER)]
    if not header_only:
        lines += list(rows or [])
    return _write_csv(path, lines)


@pytest.fixture
def applications_rows() -> list[list[str]]:
    """Synthetic application rows covering the tricky cases."""
    return [
        # Applied, awaiting response -> pending
        [
            "Acme",
            "Backend Intern",
            "Internship",
            "2026-09-01",
            "2026-09-02",
            "Application Submitted",
            "REQ-1",
            "Naukri.com",
            "Applied via portal",
            "acme|req-1",
        ],
        # Same record repeated -> must be detected as a duplicate
        [
            "Acme",
            "Backend Intern",
            "Internship",
            "2026-09-01",
            "2026-09-02",
            "Application Submitted",
            "REQ-1",
            "Naukri.com",
            "Applied via portal",
            "acme|req-1",
        ],
        # Assessment stage -> interview
        [
            "Globex",
            "Java Developer Intern",
            "Internship",
            "2026-09-05",
            "2026-09-10",
            "Assessment Invitation Received",
            "REQ-2",
            "Company Careers",
            "OA pending",
            "globex|req-2",
        ],
        # Terminal negative -> rejected
        [
            "Initech",
            "Data Science Intern",
            "Internship",
            "2026-08-05",
            "2026-08-20",
            "Not Shortlisted / Rejected",
            "REQ-3",
            "LinkedIn",
            "Rejected email",
            "initech|req-3",
        ],
        # Unknown status -> must land in "other", never pending/rejected
        [
            "Umbrella",
            "Full Stack Intern",
            "Internship",
            "2026-10-01",
            "2026-10-02",
            "Legal Hold",
            "REQ-4",
            "Referral",
            "Unknown status",
            "umbrella|req-4",
        ],
        # Unparseable + missing values -> must not crash
        ["Soylent", "QA Intern", "Internship", "not-a-date", "N/A", "TBD", "N/A", "", "", "soylent|req-5"],
        # Duplicate by fallback key (identical rows, no tracking key)
        [
            "Hooli",
            "ML Intern",
            "Internship",
            "2026-07-01",
            "2026-07-01",
            "Applied",
            "JOB-9",
            "Careers Page",
            "",
            "",
        ],
        [
            "Hooli",
            "ML Intern",
            "Internship",
            "2026-07-01",
            "2026-07-01",
            "Applied",
            "JOB-9",
            "Careers Page",
            "",
            "",
        ],
    ]


@pytest.fixture
def jobs_rows() -> list[list[str]]:
    """Synthetic listings covering skill and location matching."""
    first_listing = [
        "Infosys",
        "Java Backend Intern",
        "Pune",
        "On-site",
        "2026-11-01",
        "6 months",
        "25000",
        "B.Tech students",
        "2026-10-30",
        "Java, Spring Boot, Backend, MySQL",
        "Good fit",
        "Verified",
        "https://example.invalid/a",
        "https://example.invalid/s",
        "2026-10-10",
        "infosys|java-backend-pune",
    ]
    return [
        # Strong match: Java + Spring Boot + Backend in Pune
        first_listing,
        # Location match only
        [
            "TCS",
            "Data Analyst Intern",
            "Bengaluru",
            "Hybrid",
            "2026-11-05",
            "3 months",
            "20000",
            "Any degree",
            "2026-11-01",
            "SQL, Excel, Power BI",
            "",
            "Pending",
            "https://example.invalid/b",
            "https://example.invalid/s",
            "2026-10-11",
            "tcs|analyst",
        ],
        # Skill match only (Python + RAG + LLMs), no preferred city
        [
            "StartupX",
            "AI Engineer Intern",
            "Remote",
            "Remote",
            "2026-11-10",
            "6 months",
            "",
            "Final year",
            "2026-11-05",
            "Python, RAG, LLM APIs",
            "",
            "Verified",
            "https://example.invalid/c",
            "https://example.invalid/s",
            "2026-10-12",
            "startupx|ai",
        ],
        # No overlap at all -> score 0, must not appear by default
        [
            "Others",
            "Design Intern",
            "Chennai",
            "On-site",
            "2026-11-01",
            "2 months",
            "15000",
            "Any degree",
            "2026-11-01",
            "Figma, Photoshop",
            "",
            "Unverified",
            "https://example.invalid/d",
            "https://example.invalid/s",
            "2026-10-13",
            "others|design",
        ],
        # Duplicate of the first listing (same unique job key)
        list(first_listing),
    ]


@pytest.fixture
def data_dir(tmp_path: Path, applications_rows, jobs_rows) -> Path:
    """A temporary data directory with synthetic CSVs written to it."""
    write_applications_csv(tmp_path / "applications.csv", applications_rows)
    write_jobs_csv(tmp_path / "job_openings.csv", jobs_rows)
    return tmp_path


@pytest.fixture
def empty_jobs_dir(tmp_path: Path, applications_rows) -> Path:
    """A temporary data directory whose job_openings.csv has headers only."""
    write_applications_csv(tmp_path / "applications.csv", applications_rows)
    write_jobs_csv(tmp_path / "job_openings.csv", header_only=True)
    return tmp_path


@pytest.fixture
def missing_files_dir(tmp_path: Path) -> Path:
    """A temporary data directory with no CSV files at all."""
    return tmp_path


@pytest.fixture
def make_settings(tmp_path: Path):
    """Factory building CSV-mode :class:`Settings` around a data directory."""

    def _factory(directory: Path, **overrides: object) -> Settings:
        directory = Path(directory)
        base: dict[str, object] = {
            "data_source": "csv",
            "data_dir": directory,
            "applications_csv": directory / "applications.csv",
            "job_openings_csv": directory / "job_openings.csv",
        }
        base.update(overrides)
        return Settings(**base)  # type: ignore[arg-type]

    return _factory


@pytest.fixture
def make_client(make_settings):
    """Factory returning a ``TestClient`` bound to a data directory."""

    def _factory(directory: Path, **overrides: object) -> TestClient:
        settings = make_settings(directory, **overrides)
        return TestClient(create_app(settings), raise_server_exceptions=False)

    return _factory


@pytest.fixture
def client(make_client, data_dir: Path) -> TestClient:
    """A client wired to the synthetic two-tab dataset."""
    return make_client(data_dir)


@pytest.fixture
def empty_jobs_client(make_client, empty_jobs_dir: Path) -> TestClient:
    """A client wired to a dataset whose job tab is empty."""
    return make_client(empty_jobs_dir)


# --------------------------------------------------------------------------- #
# Real-data fixtures (read-only)
# --------------------------------------------------------------------------- #


@pytest.fixture
def real_data_copy(tmp_path: Path) -> Path:
    """Copy the project's own CSV exports into ``tmp_path``.

    The originals under ``backend/data`` are opened read-only and never
    modified; every test mutates only this temporary copy.
    """
    destination = tmp_path / "real_data"
    destination.mkdir()
    if REAL_APPLICATIONS_CSV.is_file():
        shutil.copyfile(REAL_APPLICATIONS_CSV, destination / "applications.csv")
    if REAL_JOBS_CSV.is_file():
        shutil.copyfile(REAL_JOBS_CSV, destination / "job_openings.csv")
    return destination


@pytest.fixture
def real_repository(real_data_copy: Path, make_settings) -> DataRepository:
    """A :class:`DataRepository` reading the temporary copy of the real CSVs."""
    return DataRepository(make_settings(real_data_copy))


@pytest.fixture
def real_applications(real_repository: DataRepository):
    """The normalised applications frame from the real CSV export."""
    return real_repository.get_dataset().applications


@pytest.fixture
def real_jobs(real_repository: DataRepository):
    """The normalised job frame from the real CSV export."""
    return real_repository.get_dataset().job_openings


@pytest.fixture
def real_records(real_applications) -> list[dict]:
    """Application records built from the real CSV export."""
    return build_application_records(real_applications)


@pytest.fixture
def real_job_records(real_jobs) -> list[dict]:
    """Job records built from the real CSV export."""
    return build_job_records(real_jobs)


__all__ = [
    "FIXED_NOW",
    "JOB_HEADER",
    "REAL_APPLICATIONS_CSV",
    "REAL_JOBS_CSV",
    "SHEET_HEADER",
    "write_applications_csv",
    "write_jobs_csv",
]