"""Tests for the FastAPI layer (Phase Two).

Every test runs against temporary CSV fixtures; the project's real CSV files
are only ever read (and then via a ``tmp_path`` copy).
"""

from __future__ import annotations

import inspect
import types
from pathlib import Path
from typing import Any

import gspread
import pytest
from fastapi.testclient import TestClient
from google.oauth2.service_account import Credentials

from app.config import Settings
from app.main import create_app
from app.sheets import (
    GOOGLE_SHEETS_READONLY_SCOPES,
    DataRepository,
    GoogleSheetsReader,
    GoogleSheetsUnavailableError,
)


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "ok"
        assert body["data_source"] == "csv"
        assert body["checks"]["applications_rows"] == 8  # raw rows read
        assert body["checks"]["applications_unique"] == 6  # after de-duplication
        assert body["checks"]["job_openings_rows"] == 5
        assert body["checks"]["job_openings_unique"] == 4
        assert body["checks"]["cached"] is False
        assert body["timestamp"].endswith("+00:00")

    def test_health_degrades_without_crashing(self, make_client, missing_files_dir) -> None:
        """A misconfigured source reports 'degraded' instead of 500."""
        response = make_client(missing_files_dir).get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"

    def test_health_never_leaks_paths(self, make_client, missing_files_dir) -> None:
        response = make_client(missing_files_dir).get("/api/health")
        text = response.text
        assert "not-created" not in text
        assert str(missing_files_dir) not in text
        assert "Traceback" not in text


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #


class TestDashboard:
    def test_dashboard_shape(self, client: TestClient) -> None:
        response = client.get("/api/dashboard")
        assert response.status_code == 200

        body = response.json()
        assert body["applications"]["total_applications"] == 6
        assert body["applications"]["rejected_applications"] == 1
        assert body["applications"]["pending_applications"] == 2
        assert body["applications"]["interview_applications"] == 1
        assert body["applications"]["offers"] == 0
        assert body["applications"]["unclassified_applications"] == 2
        assert body["jobs"]["total_listings"] == 4
        assert body["source"] == "csv"
        assert isinstance(body["top_matches"], list)
        assert len(body["applications"]["recent_applications"]) <= 5

    def test_dashboard_with_empty_jobs(self, empty_jobs_client: TestClient) -> None:
        response = empty_jobs_client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["jobs"]["total_listings"] == 0
        assert body["jobs"]["top_skills"] == []
        assert body["top_matches"] == []

    def test_dashboard_includes_monthly_trend(self, client: TestClient) -> None:
        months = client.get("/api/dashboard").json()["applications"]["applications_over_time"]
        assert months
        assert {"month", "count"} <= set(months[0])


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #


class TestApplicationsEndpoint:
    def test_list_applications(self, client: TestClient) -> None:
        response = client.get("/api/applications")
        assert response.status_code == 200

        body = response.json()
        assert body["total"] == 6
        assert body["page"] == 1
        assert len(body["items"]) == 6
        assert body["total_pages"] == 1

        first = body["items"][0]
        assert {"id", "company", "role", "status", "status_category"} <= set(first)

    def test_status_filter(self, client: TestClient) -> None:
        body = client.get("/api/applications", params={"status": "Rejected"}).json()
        assert body["total"] == 1
        assert body["items"][0]["status_category"] == "rejected"

    def test_status_filter_matches_category(self, client: TestClient) -> None:
        body = client.get("/api/applications", params={"status": "interview"}).json()
        assert body["total"] == 1
        assert body["items"][0]["company"] == "Globex"

    def test_platform_filter_is_case_insensitive(self, client: TestClient) -> None:
        lower = client.get("/api/applications", params={"platform": "naukri"}).json()
        upper = client.get("/api/applications", params={"platform": "NAUKRI"}).json()
        assert lower["total"] == upper["total"] == 1

    def test_company_filter(self, client: TestClient) -> None:
        assert client.get("/api/applications", params={"company": "acme"}).json()["total"] == 1

    def test_pagination(self, client: TestClient) -> None:
        first = client.get("/api/applications", params={"page": 1, "page_size": 3}).json()
        second = client.get("/api/applications", params={"page": 2, "page_size": 3}).json()

        assert first["total"] == second["total"] == 6
        assert len(first["items"]) == 3
        assert len(second["items"]) == 3
        assert first["total_pages"] == 2
        assert {r["id"] for r in first["items"]}.isdisjoint(
            {r["id"] for r in second["items"]}
        )

    def test_page_beyond_range_is_empty_not_an_error(self, client: TestClient) -> None:
        body = client.get("/api/applications", params={"page": 99, "page_size": 3}).json()
        assert body["items"] == []
        assert body["total"] == 6

    def test_available_filters_are_advertised(self, client: TestClient) -> None:
        body = client.get("/api/applications").json()
        assert "Application Submitted" in body["available_statuses"]
        assert "Naukri.com" in body["available_platforms"]

    @pytest.mark.parametrize("params", [{"page": 0}, {"page": -1}, {"page_size": 0}])
    def test_invalid_pagination_is_rejected(self, client: TestClient, params) -> None:
        assert client.get("/api/applications", params=params).status_code == 422

    def test_overlong_filter_is_rejected(self, client: TestClient) -> None:
        response = client.get("/api/applications", params={"status": "x" * 500})
        assert response.status_code == 422

    def test_blank_filter_is_ignored(self, client: TestClient) -> None:
        assert client.get("/api/applications", params={"status": "   "}).json()["total"] == 6


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #


class TestJobsEndpoint:
    def test_list_jobs(self, client: TestClient) -> None:
        response = client.get("/api/jobs")
        assert response.status_code == 200

        body = response.json()
        assert body["total"] == 4
        assert len(body["items"]) == 4
        assert body["available_locations"] == ["Bengaluru", "Chennai", "Pune", "Remote"]
        assert "Verified" in body["available_verification_statuses"]
        assert "skills" in body["items"][0]

    def test_empty_job_tab_returns_empty_page(self, empty_jobs_client: TestClient) -> None:
        response = empty_jobs_client.get("/api/jobs")
        assert response.status_code == 200

        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["total_pages"] == 0
        assert body["available_locations"] == []

    def test_location_filter(self, client: TestClient) -> None:
        body = client.get("/api/jobs", params={"location": "pune"}).json()
        assert body["total"] == 1
        assert body["items"][0]["company"] == "Infosys"

    def test_skill_filter(self, client: TestClient) -> None:
        body = client.get("/api/jobs", params={"skill": "Spring Boot"}).json()
        assert body["total"] == 1
        assert body["items"][0]["company"] == "Infosys"

    def test_verification_filter_is_exact_not_substring(self, client: TestClient) -> None:
        """"verified" must not also match "unverified"."""
        body = client.get("/api/jobs", params={"verification": "verified"}).json()
        assert body["total"] == 2
        assert all(item["verification_status"] == "Verified" for item in body["items"])

        unverified = client.get("/api/jobs", params={"verification": "unverified"}).json()
        assert unverified["total"] == 1
        assert unverified["items"][0]["company"] == "Others"

    def test_work_arrangement_filter(self, client: TestClient) -> None:
        body = client.get("/api/jobs", params={"work_arrangement": "remote"}).json()
        assert body["total"] == 1

    def test_min_match_score_filter(self, client: TestClient) -> None:
        high = client.get("/api/jobs", params={"min_match_score": 40}).json()
        assert all(
            item["company"] in {"Infosys", "TCS", "StartupX"} for item in high["items"]
        )
        best = client.get("/api/jobs", params={"min_match_score": 70}).json()
        assert best["total"] == 1
        assert best["items"][0]["company"] == "Infosys"
        assert client.get("/api/jobs", params={"min_match_score": 100}).json()["total"] == 0

    def test_pagination(self, client: TestClient) -> None:
        first = client.get("/api/jobs", params={"page": 1, "page_size": 2}).json()
        second = client.get("/api/jobs", params={"page": 2, "page_size": 2}).json()
        assert first["total_pages"] == 2
        assert len(first["items"]) == 2 and len(second["items"]) == 2

    @pytest.mark.parametrize("params", [{"min_match_score": -1}, {"min_match_score": 101}])
    def test_invalid_score_is_rejected(self, client: TestClient, params) -> None:
        assert client.get("/api/jobs", params=params).status_code == 422


# --------------------------------------------------------------------------- #
# Analytics endpoints
# --------------------------------------------------------------------------- #


class TestAnalyticsEndpoints:
    def test_application_analytics(self, client: TestClient) -> None:
        response = client.get("/api/analytics/applications")
        assert response.status_code == 200

        body = response.json()
        assert body["total_applications"] == 6
        assert body["category_counts"]["rejected"] == 1
        assert body["status_categories"]["Applied"]["category"] == "pending"
        assert body["applications_over_time"]
        assert body["generated_at"].endswith("+00:00")

    def test_job_analytics(self, client: TestClient) -> None:
        body = client.get("/api/analytics/jobs").json()
        assert body["total_listings"] == 4
        assert body["top_skills"]

    def test_job_analytics_with_no_listings(self, empty_jobs_client: TestClient) -> None:
        response = empty_jobs_client.get("/api/analytics/jobs")
        assert response.status_code == 200
        assert response.json()["total_listings"] == 0

    def test_skills_analytics(self, client: TestClient) -> None:
        response = client.get("/api/analytics/skills")
        assert response.status_code == 200

        body = response.json()
        assert body["total_listings"] == 4
        assert body["skills"]
        assert body["skills"] == sorted(
            body["skills"], key=lambda row: (-row["count"], row["skill"])
        )
        assert body["min_count"] == 1

    def test_skills_analytics_with_no_listings(self, empty_jobs_client: TestClient) -> None:
        body = empty_jobs_client.get("/api/analytics/skills").json()
        assert body["total_listings"] == 0
        assert body["skills"] == []
        assert body["unique_skills"] == 0

    def test_skills_min_count_filter(self, client: TestClient) -> None:
        assert client.get("/api/analytics/skills", params={"min_count": 2}).json()["skills"] == []
        assert client.get("/api/analytics/skills", params={"min_count": 0}).status_code == 422

    def test_matching_analytics(self, client: TestClient) -> None:
        response = client.get("/api/analytics/matching")
        assert response.status_code == 200

        body = response.json()
        assert body["total_listings"] == 4
        assert body["matched_listings"] == len(body["matches"]) == 3
        assert body["matches"][0]["company"] == "Infosys"
        assert "Java" in body["interests"]
        assert set(body["preferred_locations"]) == {
            "Bengaluru",
            "Pune",
            "Mumbai",
            "Hyderabad",
        }
        assert "heuristic" in body["scoring_note"].lower()

        top = body["matches"][0]
        assert 0 <= top["score"] <= 100
        assert top["tier"] in {"strong", "good", "moderate", "weak"}
        assert top["reasons"]
        assert top["matched_interests"]

    def test_matching_include_unmatched(self, client: TestClient) -> None:
        body = client.get(
            "/api/analytics/matching", params={"include_unmatched": True}
        ).json()
        assert len(body["matches"]) == 4
        assert any(match["score"] == 0 for match in body["matches"])

    def test_matching_with_no_listings(self, empty_jobs_client: TestClient) -> None:
        body = empty_jobs_client.get("/api/analytics/matching").json()
        assert body["matches"] == []
        assert body["total_listings"] == 0


# --------------------------------------------------------------------------- #
# Meta, docs, error handling
# --------------------------------------------------------------------------- #


class TestMisc:
    def test_meta_exposes_configuration_without_secrets(self, client: TestClient) -> None:
        body = client.get("/api/meta").json()
        assert body["data_source"] == "csv"
        assert body["applications_tab"] == "Applications"
        assert body["job_openings_tab"] == "Job Openings"
        assert "spreadsheet_id" not in body
        assert "credentials" not in body

    def test_openapi_is_served(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "/api/dashboard" in response.json()["paths"]

    def test_missing_file_returns_503_not_500(self, make_client, missing_files_dir) -> None:
        """A data-source failure is a clean 503 with a safe message."""
        response = make_client(missing_files_dir).get("/api/applications")
        assert response.status_code == 503
        assert "Traceback" not in response.text
        assert "applications.csv" in response.json()["detail"]

    def test_unknown_route_is_404_json(self, client: TestClient) -> None:
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404

    def test_cors_preflight_allows_local_frontend(self, client: TestClient) -> None:
        response = client.options(
            "/api/dashboard",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_cors_rejects_unknown_origin(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers

    def test_custom_cors_origins(self, tmp_path: Path, make_settings) -> None:
        settings = make_settings(tmp_path, cors_origins=["http://localhost:5173"])
        custom = TestClient(create_app(settings))
        response = custom.get(
            "/api/health", headers={"Origin": "http://localhost:5173"}
        )
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# --------------------------------------------------------------------------- #
# Google Sheets mode (configured but not authenticated)
# --------------------------------------------------------------------------- #


class TestGoogleSheetsMode:
    def test_not_configured_reports_degraded(self, tmp_path: Path) -> None:
        """Sheets mode without a spreadsheet ID must not crash the app."""
        settings = Settings(
            data_source="google_sheets",
            applications_csv=tmp_path / "applications.csv",
            job_openings_csv=tmp_path / "job_openings.csv",
            spreadsheet_id="",
            google_credentials_path=None,
        )
        google_client = TestClient(create_app(settings), raise_server_exceptions=False)

        health = google_client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "degraded"
        assert body["data_source"] == "google_sheets"
        assert body["checks"]["google_sheets_configured"] is False
        assert "SPREADSHEET_ID" in body["checks"]["data_error"]

        assert google_client.get("/api/dashboard").status_code == 503

    def test_real_tab_name_is_configurable(self, tmp_path: Path) -> None:
        """The Applications tab can be set to 'Sheet1' without renaming it."""
        settings = Settings(
            data_source="google_sheets",
            applications_csv=tmp_path / "applications.csv",
            job_openings_csv=tmp_path / "job_openings.csv",
            spreadsheet_id="fake-id",
            google_credentials_path=tmp_path / "missing-credentials.json",
            applications_tab="Sheet1",
        )
        client = TestClient(create_app(settings), raise_server_exceptions=False)

        body = client.get("/api/health").json()
        assert body["checks"]["applications_tab"] == "Sheet1"
        assert body["status"] == "degraded"
        assert client.get("/api/meta").json()["applications_tab"] == "Sheet1"

    def test_repository_raises_typed_error_when_unconfigured(self, tmp_path: Path) -> None:
        settings = Settings(
            data_source="google_sheets",
            spreadsheet_id="fake-id",
            google_credentials_path=None,
        )
        repository = DataRepository(settings)
        with pytest.raises(Exception) as excinfo:
            repository.get_dataset()
        assert "CREDENTIALS" in str(excinfo.value).upper() or "SPREADSHEET" in str(
            excinfo.value
        ).upper()

    def test_cache_is_invalidated_on_refresh(self, tmp_path: Path) -> None:
        """TTLCache honours invalidation so a refresh really re-reads."""
        from app.sheets import TTLCache

        calls = {"count": 0}

        class _FakeDataset:
            pass

        cache = TTLCache(ttl_seconds=300)
        dataset = _FakeDataset()
        cache.set(dataset)  # type: ignore[arg-type]
        calls["count"] += 1

        assert cache.get() is dataset
        cache.invalidate()
        assert cache.get() is None
        assert calls["count"] == 1

    def test_zero_ttl_disables_cache(self, tmp_path: Path) -> None:
        from app.sheets import TTLCache

        cache = TTLCache(ttl_seconds=0)
        cache.set(object())  # type: ignore[arg-type]
        assert cache.get() is None


# --------------------------------------------------------------------------- #
# Google Sheets reader: opening the workbook with the supported gspread API
# --------------------------------------------------------------------------- #


class _FakeWorksheet:
    """Stand-in for ``gspread.Worksheet`` that records read calls."""

    def __init__(self, title: str, values: list[list[str]]) -> None:
        self.title = title
        self._values = values
        self.calls: list[str] = []

    def get_all_values(self) -> list[list[str]]:
        self.calls.append("get_all_values")
        return self._values


class _FakeWorkbook:
    """Stand-in for ``gspread.Spreadsheet`` looked up from cached metadata."""

    def __init__(self, worksheets: list[_FakeWorksheet]) -> None:
        self._worksheets = worksheets
        self.calls: list[object] = []

    def worksheet(self, title: str) -> _FakeWorksheet:
        self.calls.append(("worksheet", title))
        for sheet in self._worksheets:
            if sheet.title == title:
                return sheet
        raise gspread.WorksheetNotFound(title)

    def worksheets(self) -> list[_FakeWorksheet]:
        self.calls.append("worksheets")
        return list(self._worksheets)


class _FakeClient:
    """Mimics ``gspread.Client``, including its rejection of unknown kwargs.

    ``gspread.Client.open_by_key(self, key)`` accepts only the spreadsheet ID.
    Passing anything else raises ``TypeError``, exactly as the real library does,
    so the regression that broke the connection cannot silently return.
    """

    def __init__(self, workbook: _FakeWorkbook) -> None:
        self._workbook = workbook
        self.open_calls: list[tuple[tuple, dict]] = []

    def open_by_key(self, *args: object, **kwargs: object) -> _FakeWorkbook:
        self.open_calls.append((args, kwargs))
        if kwargs:
            unexpected = next(iter(kwargs))
            raise TypeError(
                f"Client.open_by_key() got an unexpected keyword argument {unexpected!r}"
            )
        return self._workbook


@pytest.fixture
def fake_sheets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Factory building a :class:`GoogleSheetsReader` over a fake transport."""

    def _build(worksheets: list[_FakeWorksheet], **overrides: object) -> types.SimpleNamespace:
        credentials_file = tmp_path / "credentials.json"
        # A placeholder file only: it is never parsed, because
        # ``from_service_account_file`` is stubbed below.
        credentials_file.write_text("{}", encoding="utf-8")

        settings = Settings(  # type: ignore[arg-type]
            data_source="google_sheets",
            spreadsheet_id="sheet-id-from-config",
            google_credentials_path=credentials_file,
            applications_tab="Applications",
            job_openings_tab="Job Openings",
            sheets_read_retry_attempts=1,
            **overrides,
        )

        workbook = _FakeWorkbook(worksheets)
        client = _FakeClient(workbook)
        recorded: dict[str, Any] = {}

        monkeypatch.setattr(gspread, "authorize", lambda credentials: client)

        def _fake_from_service_account_file(
            filename: str, scopes: list[str] | None = None, **kwargs: object
        ) -> object:
            recorded["filename"] = filename
            recorded["scopes"] = list(scopes or [])
            return object()

        monkeypatch.setattr(
            Credentials, "from_service_account_file", _fake_from_service_account_file
        )

        return types.SimpleNamespace(
            reader=GoogleSheetsReader(settings),
            client=client,
            workbook=workbook,
            recorded=recorded,
            settings=settings,
        )

    return _build


class TestGoogleSheetsReaderReadOnly:
    """Opening the workbook must use the API the installed gspread supports.

    ``gspread`` has no ``readonly`` argument on ``open_by_key``; read-only access
    is enforced by the OAuth scope instead.
    """

    def test_installed_gspread_open_by_key_takes_only_the_key(self) -> None:
        """Documents the signature this code must target."""
        parameters = inspect.signature(gspread.Client.open_by_key).parameters
        assert list(parameters) == ["self", "key"]
        assert "readonly" not in parameters

    def test_open_by_key_receives_only_the_spreadsheet_id(self, fake_sheets) -> None:
        """Regression: no extra keyword arguments may be passed."""
        fake = fake_sheets([_FakeWorksheet("Applications", [["a"]])])

        fake.reader._open_workbook()

        assert len(fake.client.open_calls) == 1
        args, kwargs = fake.client.open_calls[0]
        assert args == ("sheet-id-from-config",)
        assert kwargs == {}, "open_by_key() accepts only the spreadsheet ID"

    def test_open_by_key_does_not_raise_type_error(self, fake_sheets) -> None:
        """The original failure surfaced as 'unexpected keyword argument'."""
        fake = fake_sheets([_FakeWorksheet("Applications", [["a"]])])

        workbook = fake.reader._open_workbook()  # must not raise

        assert workbook is fake.workbook

    def test_only_the_readonly_sheets_scope_is_requested(self, fake_sheets) -> None:
        """Read-only access is enforced by the scope, so it must stay narrow."""
        fake = fake_sheets([_FakeWorksheet("Applications", [["a"]])])

        fake.reader._get_client()

        scopes = fake.recorded["scopes"]
        assert scopes == list(GOOGLE_SHEETS_READONLY_SCOPES)
        assert all("readonly" in scope for scope in scopes)
        assert not any("drive" in scope for scope in scopes)
        # The full write scope is "…/auth/spreadsheets"; it must never appear.
        write_scope = "https://www.googleapis.com/auth/spreadsheets"
        assert write_scope not in scopes

    def test_credentials_path_is_passed_to_the_google_library(self, fake_sheets) -> None:
        fake = fake_sheets([_FakeWorksheet("Applications", [["a"]])])

        fake.reader._get_client()

        assert str(fake.recorded["filename"]).endswith("credentials.json")

    def test_read_tab_performs_only_read_calls(self, fake_sheets) -> None:
        """A full read touches exactly two methods, both read-only."""
        sheet = _FakeWorksheet("Applications", [["Company", "Role"], ["Acme", "Dev"]])
        fake = fake_sheets([sheet])

        frame = fake.reader.read_tab("Applications")

        assert sheet.calls == ["get_all_values"]
        assert fake.workbook.calls == [("worksheet", "Applications")]
        assert frame.shape == (2, 2)
        assert frame.iloc[0, 0] == "Company"

    def test_missing_tab_is_reported_as_a_tab_problem(self, fake_sheets) -> None:
        fake = fake_sheets([_FakeWorksheet("Applications", [["a"]])])

        with pytest.raises(GoogleSheetsUnavailableError) as excinfo:
            fake.reader.read_tab("Job Openings")

        assert "Job Openings" in str(excinfo.value)

    def test_repository_loads_a_dataset_through_the_reader(self, fake_sheets) -> None:
        """End-to-end: the fixed connection path yields a real Dataset."""
        applications = _FakeWorksheet(
            "Applications",
            [
                [
                    "",
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
                ],
                [
                    "",
                    "Acme",
                    "Backend Intern",
                    "Internship",
                    "2026-09-01",
                    "2026-09-02",
                    "Application Submitted",
                    "REQ-1",
                    "Naukri.com",
                    "",
                    "acme|req-1",
                ],
            ],
        )
        jobs = _FakeWorksheet(
            "Job Openings",
            [
                [
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
            ],
        )
        fake = fake_sheets([applications, jobs])

        dataset = DataRepository(fake.settings, reader=fake.reader).get_dataset()

        assert dataset.source == "google_sheets"
        assert dataset.applications_rows == 1
        assert dataset.job_openings_rows == 0
        assert list(dataset.applications["company"]) == ["Acme"]
        assert list(dataset.applications["status"]) == ["Application Submitted"]

    def test_reader_exposes_no_write_operations(self) -> None:
        """Guard against a mutating method ever being added to this class."""
        forbidden = {
            "add_worksheet",
            "append",
            "append_row",
            "append_rows",
            "batch_update",
            "clear",
            "create",
            "del_worksheet",
            "delete",
            "delete_row",
            "delete_rows",
            "duplicate_sheet",
            "format",
            "insert_row",
            "insert_rows",
            "merge_cells",
            "rename",
            "resize",
            "sort",
            "update",
            "update_cell",
            "update_cells",
        }
        exposed = {name.lower() for name in dir(GoogleSheetsReader)}
        assert exposed.isdisjoint(forbidden)