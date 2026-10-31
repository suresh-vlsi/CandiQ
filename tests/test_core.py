from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from derived import compute_derived
from llm import _quote_check
from schemas import Claim, Evidence, Verdict, Criterion, Priority, ParsedRequest
from pipeline import score_candidate


def make_claim(path="profile.name", value="Asha", record_id="p1"):
    return Claim(id="cl1", candidate_id="p1", criterion_id="c1", text="Candidate name is Asha",
                 evidence=[Evidence(record_type="person", record_id=record_id, field_path=path, value=value)])


def test_exact_field_path_is_required():
    records = {"p1": {"profile": {"name": "Asha"}, "other": "Asha"}}
    claim = make_claim()
    assert _quote_check(claim, records)


def test_value_existing_elsewhere_does_not_pass():
    records = {"p1": {"profile": {"name": "Different"}, "other": "Asha"}}
    claim = make_claim()
    assert not _quote_check(claim, records)
    assert claim.verdict == Verdict.UNSUPPORTED


def test_missing_path_rejected():
    claim = make_claim(path="profile.missing")
    assert not _quote_check(claim, {"p1": {"profile": {"name": "Asha"}}})


def test_array_index_path():
    claim = make_claim(path="jobs[0].title", value="Engineer")
    assert _quote_check(claim, {"p1": {"jobs": [{"title": "Engineer"}]}})


def test_unknown_criteria_report_coverage_and_review():
    req = ParsedRequest(role_title="Engineer", criteria=[
        Criterion(id="c1", text="Python", priority=Priority.MUST, category="skill")], search_variants=[])
    report = score_candidate("p1", "Asha", [], req)
    assert report.score == 0
    assert report.evidence_coverage == 0
    assert report.recommendation_status == "needs_review"


def test_confirmed_must_have_contradiction_not_recommended():
    req = ParsedRequest(role_title="Engineer", criteria=[
        Criterion(id="c1", text="Python", priority=Priority.MUST, category="skill")], search_variants=[])
    claim = make_claim(); claim.criterion_id = "c1"; claim.verdict = Verdict.CONTRADICTED
    report = score_candidate("p1", "Asha", [claim], req)
    assert report.recommendation_status == "not_recommended"
    assert report.evidence_coverage == 100


def test_derived_experience_handles_month_precision():
    person = {"experience": {"employment_details": {"current": [
        {"name": "Example", "title": "Engineer", "start_date": "2024-01"}], "past": []}}}
    result = compute_derived(person, date(2025, 1, 1))
    assert result["total_experience"].startswith("1.0 years")


def test_hyderabad_candidate_fails_bengaluru_location_requirement():
    req = ParsedRequest(
        role_title="Senior ASIC Physical Design Engineer",
        criteria=[Criterion(id="loc1", text="Bengaluru, India",
                            priority=Priority.MUST, category="location")],
        search_variants=[]
    )
    claim = Claim(
        id="loc-claim", candidate_id="p1", criterion_id="loc1",
        text="Candidate is located in Hyderabad, Telangana, India",
        evidence=[
            Evidence(record_type="person", record_id="p1",
                     field_path="basic_profile.location.city", value="Hyderabad"),
            Evidence(record_type="person", record_id="p1",
                     field_path="basic_profile.location.country", value="India"),
        ],
        verdict=Verdict.SUPPORTED
    )
    record = {"basic_profile": {"location": {
        "city": "Hyderabad", "country": "India",
        "raw": "Hyderabad, Telangana, India"
    }}}
    report = score_candidate("p1", "Candidate", [claim], req, candidate_record=record)
    assert report.criterion_scores[0].met == "no"
    assert report.recommendation_status == "not_recommended"


def test_bangalore_alias_matches_bengaluru_location_requirement():
    req = ParsedRequest(
        role_title="Engineer",
        criteria=[Criterion(id="loc1", text="Bengaluru, India",
                            priority=Priority.MUST, category="location")],
        search_variants=[]
    )
    record = {"basic_profile": {"location": {
        "city": "Bangalore", "country": "India"
    }}}
    report = score_candidate("p1", "Candidate", [], req, candidate_record=record)
    assert report.criterion_scores[0].met == "yes"
    assert report.recommendation_status != "not_recommended"


def test_location_requirement_is_unknown_when_source_location_missing():
    req = ParsedRequest(
        role_title="Engineer",
        criteria=[Criterion(id="loc1", text="Bengaluru, India",
                            priority=Priority.MUST, category="location")],
        search_variants=[]
    )
    report = score_candidate("p1", "Candidate", [], req, candidate_record={})
    assert report.criterion_scores[0].met == "unknown"
    assert report.recommendation_status == "needs_review"
