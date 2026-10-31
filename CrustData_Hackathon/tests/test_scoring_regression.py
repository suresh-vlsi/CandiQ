"""Regression tests for evidence-backed candidate scoring."""
from schemas import Criterion, Priority, ParsedRequest, Claim, Verdict
from pipeline import score_candidate


def make_request():
    return ParsedRequest(
        role_title="Senior ASIC Physical Design Engineer",
        criteria=[
            Criterion(id="c1", text="ASIC physical design experience",
                      priority=Priority.MUST, category="skill"),
            Criterion(id="c2", text="Senior level",
                      priority=Priority.MUST, category="seniority"),
            Criterion(id="c3", text="Synopsys tools",
                      priority=Priority.NICE, category="skill"),
            Criterion(id="c4", text="Timing analysis",
                      priority=Priority.NICE, category="skill"),
        ],
        search_variants=[
            {"name": "strict", "titles": ["Senior ASIC Physical Design Engineer"]},
            {"name": "relaxed"},
            {"name": "adjacent"},
        ],
    )


def supported_claim(cid, text):
    from schemas import Evidence
    return Claim(
        id=f"claim-{cid}", candidate_id="123", criterion_id=cid, text=text,
        evidence=[Evidence(record_type="person", record_id="123",
                           field_path="basic_profile.current_title",
                           value="Senior ASIC Physical Design Engineer")],
        verdict=Verdict.SUPPORTED,
    )


def test_unknown_nice_to_have_reduces_score_but_not_coverage():
    request = make_request()
    claims = [supported_claim("c1", "ASIC physical design experience"),
              supported_claim("c2", "Senior level"),
              supported_claim("c4", "Timing analysis")]
    report = score_candidate("123", "Candidate", claims, request)
    # weights: 3 + 3 + 1 unknown + 1 yes = 7 earned / 8 total
    assert report.score == 87.5
    assert report.evidence_coverage == 87.5
    assert report.recommendation_status == "strong_match"


def test_all_assessable_positive_does_not_make_unknown_criteria_disappear():
    request = make_request()
    claims = [supported_claim("c1", "ASIC physical design experience"),
              supported_claim("c2", "Senior level")]
    report = score_candidate("123", "Candidate", claims, request)
    assert report.score == 75.0
    assert report.evidence_coverage == 75.0


def test_unknown_must_have_requires_review():
    request = make_request()
    claims = [supported_claim("c1", "ASIC physical design experience")]
    report = score_candidate("123", "Candidate", claims, request)
    assert report.recommendation_status == "needs_review"


def test_confirmed_must_have_contradiction_is_not_recommended():
    request = make_request()
    claims = [
        supported_claim("c2", "Senior level"),
    ]
    from schemas import Evidence
    claims.append(Claim(
        id="negative", candidate_id="123", criterion_id="c1",
        text="No ASIC physical design experience",
        evidence=[Evidence(record_type="person", record_id="123",
                           field_path="basic_profile.current_title", value="Other")],
        verdict=Verdict.CONTRADICTED,
    ))
    report = score_candidate("123", "Candidate", claims, request)
    assert report.recommendation_status == "not_recommended"
