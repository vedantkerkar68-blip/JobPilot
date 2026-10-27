"""Tests for the analytics engine (Phase One).

Covers: the real CSV layout, empty job data, missing values, unknown statuses,
date parsing, duplicate detection, skill matching and location matching.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from app.analytics import (
    application_analytics,
    applications_over_time,
    build_application_records,
    build_dashboard,
    build_job_records,
    categorise_status,
    deduplicate_records,
    job_analytics,
    match_jobs,
    score_job_match,
    top_skills,
)
from app.sheets import (
    DataFileNotFoundError,
    DataRepository,
    normalise_frame,
    normalise_header,
    read_csv_sheet,
    APPLICATION_COLUMN_ALIASES,
    APPLICATION_DATE_COLUMNS,
    JOB_COLUMN_ALIASES,
    JOB_DATE_COLUMNS,
    is_missing,
)
from conftest import FIXED_NOW, write_applications_csv, write_jobs_csv


# --------------------------------------------------------------------------- #
# Header / layout normalisation
# --------------------------------------------------------------------------- #


class TestLayoutHandling:
    """The exported sheet has a title block; the header is on row 7."""

    def test_header_found_on_row_seven(self, real_applications: pd.DataFrame) -> None:
        """The title block and summary row must not be treated as data."""
        assert "company" in real_applications.columns
        assert "status" in real_applications.columns
        # The banner text from row 2 and the summary stats from row 4 are gone.
        joined = " ".join(
            str(value) for value in real_applications.to_numpy().ravel().tolist()
        )
        assert "Job & Internship Application Tracker" not in joined
        assert "Active Applications" not in joined

    def test_unnamed_first_column_is_dropped(self, real_applications: pd.DataFrame) -> None:
        """The empty spreadsheet gutter column must not survive."""
        assert "unnamed_0" not in real_applications.columns
        assert not any(name.startswith("Unnamed") for name in real_applications.columns)

    def test_normalise_header_handles_real_headers(self) -> None:
        assert normalise_header("Role/Position") == "role_position"
        assert normalise_header(" Platform/Portal ") == "platform_portal"
        assert normalise_header("Job ID/Req ID") == "job_id_req_id"
        assert normalise_header("") == ""
        assert normalise_header(None) == ""

    def test_header_only_file_yields_empty_frame(self, tmp_path) -> None:
        """A tab with headers and no records must load cleanly."""
        path = write_jobs_csv(tmp_path / "job_openings.csv", header_only=True)
        frame = read_csv_sheet(path, JOB_COLUMN_ALIASES, JOB_DATE_COLUMNS)
        assert frame.empty
        assert "company" in frame.columns
        assert "required_skills" in frame.columns

    def test_plain_header_row_also_works(self, tmp_path) -> None:
        """CSVs without a preamble are still detected correctly."""
        path = write_applications_csv(
            tmp_path / "applications.csv",
            [["Acme", "Dev Intern", "Internship", "2026-09-01", "2026-09-01",
              "Applied", "1", "Site", "", "acme|1"]],
            with_preamble=False,
        )
        frame = read_csv_sheet(path, APPLICATION_COLUMN_ALIASES, APPLICATION_DATE_COLUMNS)
        assert len(frame) == 1
        assert frame.loc[0, "company"] == "Acme"

    def test_missing_file_raises_clear_error(self, tmp_path) -> None:
        """A missing CSV is reported, not silently treated as empty."""
        with pytest.raises(DataFileNotFoundError):
            read_csv_sheet(tmp_path / "nope.csv", JOB_COLUMN_ALIASES, JOB_DATE_COLUMNS)

    def test_empty_frame_input_is_safe(self) -> None:
        """normalise_frame tolerates a completely empty sheet."""
        assert normalise_frame(pd.DataFrame(), JOB_COLUMN_ALIASES, JOB_DATE_COLUMNS).empty


# --------------------------------------------------------------------------- #
# Missing values
# --------------------------------------------------------------------------- #


class TestMissingValues:
    @pytest.mark.parametrize(
        "value", ["", "  ", "N/A", "n/a", "NA", "None", "null", "-", "NaN", None]
    )
    def test_placeholder_tokens_count_as_missing(self, value) -> None:
        assert is_missing(value)

    @pytest.mark.parametrize("value", ["Applied", "Naukri.com", "2026-09-01", "0"])
    def test_real_values_are_not_missing(self, value) -> None:
        assert not is_missing(value)

    def test_missing_fields_are_counted_not_fatal(self, data_dir) -> None:
        """Rows with 'N/A' and blanks produce counts, not exceptions."""
        repository = DataRepository(_settings_for(data_dir))
        analytics = application_analytics(repository.get_dataset().applications)

        assert analytics["total_applications"] == 6  # 8 rows, 2 duplicates removed
        assert analytics["missing_data_counts"]["platform"] >= 1
        assert analytics["missing_data_counts"]["application_date"] >= 1
        assert analytics["missing_data_counts"]["job_id"] >= 1


# --------------------------------------------------------------------------- #
# Status categorisation
# --------------------------------------------------------------------------- #


class TestStatusCategorisation:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("Application Submitted", "pending"),
            ("No Change", "pending"),
            ("Drive Announcement Received", "pending"),
            ("Applied", "pending"),
            ("Assessment Invitation Received", "interview"),
            ("Assessment Completed & Submitted", "interview"),
            ("Not Shortlisted / Rejected", "rejected"),
            ("Rejected", "rejected"),
        ],
    )
    def test_observed_statuses_map_correctly(self, status: str, expected: str) -> None:
        """Every status currently in the spreadsheet maps as documented."""
        assert categorise_status(status) == expected

    @pytest.mark.parametrize(
        "status",
        ["Legal Hold", "Quantum flux", "Wingardium Leviosa", "", "N/A", None],
    )
    def test_unknown_statuses_are_never_guessed(self, status) -> None:
        """Unknown statuses must fall into 'other', not pending or rejected."""
        assert categorise_status(status) == "other"

    def test_rule_order_prefers_interview_over_submitted(self) -> None:
        """"Assessment ... Submitted" is interview-stage, not pending."""
        assert categorise_status("Assessment Completed & Submitted") == "interview"

    def test_categories_are_mutually_exclusive_and_total(
        self, real_applications: pd.DataFrame
    ) -> None:
        """pending + interview + rejected + offer + other == total."""
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        counts = analytics["category_counts"]
        assert set(counts) == {"pending", "interview", "rejected", "offer", "other"}
        assert sum(counts.values()) == analytics["total_applications"]

    def test_unclassified_is_reported_separately(self, data_dir) -> None:
        """'Legal Hold' and 'TBD' must show up as unclassified, not pending."""
        repository = DataRepository(_settings_for(data_dir))
        analytics = application_analytics(repository.get_dataset().applications, now=FIXED_NOW)
        assert analytics["unclassified_applications"] == 2
        assert analytics["category_counts"]["other"] == 2
        assert analytics["category_counts"]["pending"] == 2

    def test_status_categories_map_is_exposed(self, real_applications) -> None:
        """The API can explain how each observed status was categorised."""
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        mapping = analytics["status_categories"]
        assert mapping["Not Shortlisted / Rejected"]["category"] == "rejected"
        assert mapping["Application Submitted"]["category"] == "pending"
        assert mapping["Application Submitted"]["count"] == 9


# --------------------------------------------------------------------------- #
# Real dataset shape
# --------------------------------------------------------------------------- #


class TestRealApplicationsDataset:
    """Assertions about the actual applications.csv shipped with the project."""

    def test_row_count_matches_spreadsheet_summary(
        self, real_applications: pd.DataFrame
    ) -> None:
        """The sheet's own summary says 25; we must find 25 data rows."""
        records = build_application_records(real_applications)
        assert len(records) == 25

    def test_columns_are_normalised(self, real_applications: pd.DataFrame) -> None:
        expected = {
            "company",
            "role",
            "application_type",
            "application_date",
            "latest_update_date",
            "status",
            "job_id",
            "platform",
            "notes",
            "tracking_key",
        }
        assert expected.issubset(set(real_applications.columns))

    def test_real_status_totals(self, real_applications: pd.DataFrame) -> None:
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        counts = analytics["status_counts"]

        assert counts["Not Shortlisted / Rejected"] == 9
        assert counts["Application Submitted"] == 9
        assert counts["No Change"] == 2
        assert counts["Assessment Completed & Submitted"] == 1
        assert counts["Drive Announcement Received"] == 1
        assert counts["Assessment Invitation Received"] == 1
        assert counts["Applied"] == 1
        assert counts["Rejected"] == 1

        assert analytics["rejected_applications"] == 10
        assert analytics["offers"] == 0
        assert analytics["interview_applications"] == 2
        assert analytics["pending_applications"] == 13
        assert analytics["unclassified_applications"] == 0

    def test_monthly_trend_matches_application_dates(
        self, real_applications: pd.DataFrame
    ) -> None:
        months = applications_over_time(real_applications)
        by_month = {row["month"]: row["count"] for row in months}

        assert months == sorted(months, key=lambda row: row["month"])
        assert sum(by_month.values()) == 21  # 25 rows, 4 without a date
        assert set(by_month) == {"2026-08", "2026-09", "2026-10"}
        assert by_month["2026-08"] == 7

    def test_platform_grouping_is_case_insensitive(
        self, real_applications: pd.DataFrame
    ) -> None:
        """"Naukri.com" and "naukri.com" are one platform, not two."""
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        platforms = {row["platform"]: row["count"] for row in analytics["applications_by_platform"]}
        naukri = [name for name in platforms if "naukri" in name.lower()]
        assert len(naukri) == 1
        assert platforms[naukri[0]] == 3

    def test_recent_applications_are_newest_first(self, real_records: list[dict]) -> None:
        recent = application_analytics(
            pd.DataFrame(), recent_limit=3
        )  # empty -> empty recent list
        assert recent["recent_applications"] == []

    def test_real_data_has_no_duplicates(self, real_applications: pd.DataFrame) -> None:
        """All 25 tracking keys in the sheet are distinct."""
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        assert analytics["duplicate_groups"] == []
        assert analytics["total_applications"] == 25


# --------------------------------------------------------------------------- #
# Date parsing
# --------------------------------------------------------------------------- #


class TestDateParsing:
    def test_iso_dates_are_parsed(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        frame = repository.get_dataset().applications
        parsed = frame.loc[frame["company"] == "Acme", "application_date"].iloc[0]
        assert pd.notna(parsed)
        assert pd.Timestamp(parsed) == pd.Timestamp("2026-09-01")

    def test_unparseable_dates_become_nat(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        frame = repository.get_dataset().applications
        bad = frame.loc[frame["company"] == "Soylent", "application_date"].iloc[0]
        assert pd.isna(bad)

    def test_na_date_is_not_a_value(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        frame = repository.get_dataset().applications
        update = frame.loc[frame["company"] == "Soylent", "latest_update_date"].iloc[0]
        assert pd.isna(update)

    def test_records_expose_iso_dates_or_none(self, real_records: list[dict]) -> None:
        for record in real_records:
            for field in ("application_date", "latest_update_date"):
                value = record[field]
                assert value is None or len(value) == 10
                if value is not None:
                    datetime.strptime(value, "%Y-%m-%d")

    def test_rows_without_dates_are_excluded_from_trend(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        months = applications_over_time(repository.get_dataset().applications)
        assert sum(row["count"] for row in months) == 5  # 6 unique rows, 1 has no date


# --------------------------------------------------------------------------- #
# Duplicate detection
# --------------------------------------------------------------------------- #


class TestDuplicateDetection:
    def test_duplicate_tracking_key_is_collapsed(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        analytics = application_analytics(repository.get_dataset().applications, now=FIXED_NOW)

        assert analytics["total_applications"] == 6
        assert analytics["duplicate_groups"], "the repeated Acme row must be reported"

        # Both de-duplication tiers fire: the repeated Acme row shares a
        # Tracking Key, the repeated Hooli row has none and falls back.
        by_tier = {group["key_tier"]: group for group in analytics["duplicate_groups"]}
        assert set(by_tier) == {"tracking_key", "company_role_job_id"}
        assert all(group["count"] == 1 for group in by_tier.values())

    def test_fallback_company_role_job_id_match(self) -> None:
        records = [
            {"company": "Acme", "role": "Dev", "job_id": "1", "application_date": "2026-01-01"},
            {"company": "acme", "role": "dev", "job_id": "1", "application_date": "2026-01-02"},
        ]
        unique, duplicates = deduplicate_records(records)
        assert len(unique) == 1
        assert duplicates[0]["key_tier"] == "company_role_job_id"

    def test_tracking_key_wins_over_looser_tiers(self) -> None:
        """A different tracking key means a genuinely different application."""
        records = [
            {
                "company": "Acme",
                "role": "Dev",
                "job_id": "1",
                "application_date": "2026-01-01",
                "tracking_key": "acme|req-1",
            },
            {
                "company": "Acme",
                "role": "Dev",
                "job_id": "1",
                "application_date": "2026-01-01",
                "tracking_key": "acme|req-2",
            },
        ]
        unique, duplicates = deduplicate_records(records)
        assert len(unique) == 2
        assert duplicates == []

    def test_company_role_fallback_ignores_identical_rows_without_ids(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        records = build_application_records(repository.get_dataset().applications)
        hooli = [r for r in records if r["company"] == "Hooli"]
        assert len(hooli) == 1

    def test_empty_input_is_safe(self) -> None:
        unique, duplicates = deduplicate_records([])
        assert unique == [] and duplicates == []

    def test_job_duplicates_are_collapsed(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        analytics = job_analytics(repository.get_dataset().job_openings, now=FIXED_NOW)
        assert analytics["total_listings"] == 4  # 5 rows, 1 duplicate removed
        assert analytics["duplicate_groups"]


# --------------------------------------------------------------------------- #
# Applications analytics
# --------------------------------------------------------------------------- #


class TestApplicationAnalytics:
    def test_totals_reconcile(self, real_applications) -> None:
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        assert analytics["total_applications"] == sum(
            row["count"] for row in analytics["applications_by_platform"]
        ) + analytics["missing_data_counts"].get("platform", 0)

    def test_active_and_rejected_are_complementary(self, real_applications) -> None:
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        assert (
            analytics["active_applications"] + analytics["rejected_applications"]
            == analytics["total_applications"]
        )

    def test_response_rate_is_a_percentage(self, real_applications) -> None:
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        assert 0.0 <= analytics["response_rate_percent"] <= 100.0
        assert analytics["response_rate_percent"] == 40.0  # 10 decided / 25

    def test_recent_applications_sorted_newest_first(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        analytics = application_analytics(
            repository.get_dataset().applications, recent_limit=4, now=FIXED_NOW
        )
        stamps = [
            record["latest_update_date"] or record["application_date"] or ""
            for record in analytics["recent_applications"]
        ]
        assert stamps == sorted(stamps, reverse=True)
        assert len(analytics["recent_applications"]) == 4

    def test_generated_at_is_timezone_aware_utc(self, real_applications) -> None:
        analytics = application_analytics(real_applications, now=FIXED_NOW)
        parsed = datetime.fromisoformat(analytics["generated_at"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(None)

    def test_empty_frame_returns_zeroes(self) -> None:
        analytics = application_analytics(pd.DataFrame(), now=FIXED_NOW)
        assert analytics["total_applications"] == 0
        assert analytics["applications_over_time"] == []
        assert analytics["response_rate_percent"] == 0.0
        assert sum(analytics["category_counts"].values()) == 0

    def test_none_frame_returns_zeroes(self) -> None:
        assert application_analytics(None, now=FIXED_NOW)["total_applications"] == 0


# --------------------------------------------------------------------------- #
# Job analytics
# --------------------------------------------------------------------------- #


class TestJobAnalytics:
    def test_header_only_tab_is_handled(self, empty_jobs_dir) -> None:
        """The current Job Openings tab is empty; nothing may break or appear."""
        repository = DataRepository(_settings_for(empty_jobs_dir))
        analytics = job_analytics(repository.get_dataset().job_openings, now=FIXED_NOW)

        assert analytics["total_listings"] == 0
        assert analytics["listings_by_location"] == []
        assert analytics["listings_by_company"] == []
        assert analytics["listings_by_work_arrangement"] == []
        assert analytics["top_skills"] == []
        assert analytics["listings_by_verification_status"] == []

    def test_no_fake_listings_are_invented(self, empty_jobs_dir) -> None:
        repository = DataRepository(_settings_for(empty_jobs_dir))
        assert build_job_records(repository.get_dataset().job_openings) == []

    def test_aggregations_on_populated_data(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        analytics = job_analytics(repository.get_dataset().job_openings, now=FIXED_NOW)

        assert analytics["total_listings"] == 4
        locations = {row["location"]: row["count"] for row in analytics["listings_by_location"]}
        assert locations["Pune"] == 1
        assert locations["Bengaluru"] == 1
        arrangements = {
            row["work_arrangement"] for row in analytics["listings_by_work_arrangement"]
        }
        assert arrangements == {"On-site", "Hybrid", "Remote"}
        verifications = {
            row["verification_status"] for row in analytics["listings_by_verification_status"]
        }
        assert verifications == {"Verified", "Pending", "Unverified"}

    def test_missing_fields_are_counted(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        analytics = job_analytics(repository.get_dataset().job_openings, now=FIXED_NOW)
        assert analytics["missing_data_counts"].get("stipend", 0) >= 1

    def test_empty_frame_returns_zeroes(self) -> None:
        analytics = job_analytics(pd.DataFrame(), now=FIXED_NOW)
        assert analytics["total_listings"] == 0
        assert analytics["duplicate_groups"] == []

    def test_skills_are_split_and_counted(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        skills = top_skills(repository.get_dataset().job_openings)
        names = [row["skill"] for row in skills]
        assert "Java" in names
        assert "Spring Boot" in names
        assert "SQL" in names
        assert skills == sorted(skills, key=lambda row: (-row["count"], row["skill"]))

    def test_min_count_filter(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        assert top_skills(repository.get_dataset().job_openings, min_count=2) == []
        assert len(top_skills(repository.get_dataset().job_openings, min_count=1)) > 0


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


class TestSkillMatching:
    def test_java_spring_boot_backend_scores_high(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        matches = match_jobs(repository.get_dataset().job_openings)
        top = matches[0]
        assert top["company"] == "Infosys"
        assert "Java" in top["matched_interests"]
        assert "Spring Boot" in top["matched_interests"]
        assert top["score"] >= 60
        assert top["tier"] == "strong"

    def test_python_rag_llm_is_detected(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        matches = match_jobs(repository.get_dataset().job_openings)
        startup = next(m for m in matches if m["company"] == "StartupX")
        assert "Python" in startup["matched_interests"]
        assert "RAG" in startup["matched_interests"]
        assert "LLMs" in startup["matched_interests"]

    def test_no_overlap_scores_zero_and_is_excluded(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        default_matches = match_jobs(repository.get_dataset().job_openings)
        assert all(m["company"] != "Others" for m in default_matches)

        with_unmatched = match_jobs(
            repository.get_dataset().job_openings, include_unmatched=True
        )
        design = next(m for m in with_unmatched if m["company"] == "Others")
        assert design["score"] == 0.0
        assert design["tier"] == "weak"
        assert design["matched_interests"] == []

    def test_reasons_are_explainable(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        for match in match_jobs(repository.get_dataset().job_openings):
            assert match["reasons"], "every match must explain itself"
            assert all(isinstance(reason, str) and reason for reason in match["reasons"])

    def test_title_signal_scores_lower_than_a_skills_signal(self) -> None:
        """The same interest found in the title alone is worth less than in skills."""
        title_only = score_job_match(
            {"id": 1, "skills": [], "title": "Java Intern", "location": ""}
        )
        skills_only = score_job_match(
            {"id": 2, "skills": ["Java"], "title": "Intern", "location": ""}
        )
        assert title_only["score"] < skills_only["score"]
        assert title_only["matched_interests"] == ["Java"]
        assert skills_only["matched_interests"] == ["Java"]

    def test_short_circuits_do_not_match_inside_words(self) -> None:
        """"ai" must not match "mysql" and "ml" must not match "email"."""
        record = {"id": 1, "skills": ["MySQL", "Email"], "title": "", "location": ""}
        assert score_job_match(record)["matched_interests"] == []

    def test_empty_jobs_produce_no_matches(self, empty_jobs_dir) -> None:
        repository = DataRepository(_settings_for(empty_jobs_dir))
        assert match_jobs(repository.get_dataset().job_openings) == []

    def test_matches_are_sorted_by_score(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        scores = [m["score"] for m in match_jobs(repository.get_dataset().job_openings)]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        matches = match_jobs(repository.get_dataset().job_openings, min_score=40.0)
        assert all(m["score"] >= 40.0 for m in matches)

    def test_limit_is_respected(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        assert len(match_jobs(repository.get_dataset().job_openings, limit=1)) == 1


class TestLocationMatching:
    def test_pune_is_preferred(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        matches = match_jobs(repository.get_dataset().job_openings)
        infosys = next(m for m in matches if m["company"] == "Infosys")
        assert infosys["matched_locations"] == ["Pune"]
        assert any("Pune" in reason for reason in infosys["reasons"])

    def test_bengaluru_spelling_variant_matches(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        matches = match_jobs(repository.get_dataset().job_openings)
        tcs = next(m for m in matches if m["company"] == "TCS")
        assert tcs["matched_locations"] == ["Bengaluru"]

    def test_remote_is_not_a_preferred_city(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        matches = match_jobs(repository.get_dataset().job_openings)
        startup = next(m for m in matches if m["company"] == "StartupX")
        assert startup["matched_locations"] == []

    @pytest.mark.parametrize("city", ["Hyderabad", "Mumbai", "Bangalore"])
    def test_all_preferred_cities_are_recognised(self, city: str) -> None:
        match = score_job_match({"id": 1, "skills": [], "title": "", "location": city})
        assert match["score"] > 0
        assert match["matched_locations"]

    def test_chennai_is_not_preferred(self) -> None:
        match = score_job_match(
            {"id": 1, "skills": ["Java"], "title": "", "location": "Chennai"}
        )
        assert match["matched_locations"] == []
        assert match["score"] > 0  # still a skill match


# --------------------------------------------------------------------------- #
# Dashboard aggregation
# --------------------------------------------------------------------------- #


class TestDashboardSummary:
    def test_dashboard_uses_dataset_metadata(self, data_dir) -> None:
        repository = DataRepository(_settings_for(data_dir))
        summary = build_dashboard(repository.get_dataset(), now=FIXED_NOW)

        assert summary.source == "csv"
        assert summary.applications["total_applications"] == 6
        assert summary.jobs["total_listings"] == 4
        assert len(summary.top_matches) <= 5
        assert summary.fetched_at.tzinfo is not None

    def test_dashboard_with_empty_jobs(self, empty_jobs_dir) -> None:
        repository = DataRepository(_settings_for(empty_jobs_dir))
        summary = build_dashboard(repository.get_dataset(), now=FIXED_NOW)
        assert summary.jobs["total_listings"] == 0
        assert summary.top_matches == []


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _settings_for(directory):
    """Build CSV-mode settings for a temporary data directory."""
    from app.config import Settings

    return Settings(
        data_source="csv",
        data_dir=directory,
        applications_csv=directory / "applications.csv",
        job_openings_csv=directory / "job_openings.csv",
    )