"""Regression tests for deterministic semiconductor skill mapping."""
from schemas import Criterion, Priority, ParsedRequest, Claim, Evidence, Verdict
from pipeline import (_deterministic_skill_result, _seniority_result, _deduplicate_claims,
                      _apply_skill_evidence_guard, score_candidate)

def criterion(text, category='skill', priority=Priority.NICE, cid='x'):
    return Criterion(id=cid, text=text, priority=priority, category=category)

def person(skills=None, title='', headline=''):
    return {'basic_profile': {'current_title': title, 'headline': headline},
            'skills': {'professional_network_skills': skills or []}}

def test_primetime_is_synopsys_and_timing_evidence():
    record = person(['PrimeTime'])
    assert _deterministic_skill_result(criterion('experience with Synopsys tools'), record) == 'yes'
    assert _deterministic_skill_result(criterion('timing analysis'), record) == 'yes'

def test_innovus_does_not_prove_synopsys_experience():
    assert _deterministic_skill_result(criterion('experience with Synopsys tools'), person(['Innovus'])) == 'unknown'

def test_sta_proves_timing_but_not_vendor():
    record = person(['STA'])
    assert _deterministic_skill_result(criterion('timing analysis'), record) == 'yes'
    assert _deterministic_skill_result(criterion('Synopsys tools'), record) == 'unknown'

def test_place_and_route_supports_placement_and_routing_only():
    record = person(['Place & Route'])
    assert _deterministic_skill_result(criterion('placement'), record) == 'yes'
    assert _deterministic_skill_result(criterion('routing'), record) == 'yes'
    assert _deterministic_skill_result(criterion('floorplanning'), record) == 'unknown'

def test_seniority_is_extracted_from_full_title():
    c = criterion('senior', category='seniority', priority=Priority.MUST)
    assert _seniority_result(c, person(title='ASIC Physical Design Senior Engineer')) == 'yes'

def test_missing_tool_evidence_remains_unknown_not_no():
    assert _deterministic_skill_result(criterion('Synopsys tools'), person(['Physical Design', 'STA'])) == 'unknown'

def test_duplicate_claims_are_removed_but_distinct_criteria_retained():
    evidence = [Evidence(record_type='person', record_id='p1', field_path='skills.professional_network_skills[3]', value='PrimeTime')]
    a = Claim(id='a', candidate_id='p1', criterion_id='c1', text='PrimeTime skill', evidence=evidence, verdict=Verdict.SUPPORTED)
    b = Claim(id='b', candidate_id='p1', criterion_id='c1', text='PrimeTime skill', evidence=evidence, verdict=Verdict.SUPPORTED)
    c = Claim(id='c', candidate_id='p1', criterion_id='c2', text='PrimeTime supports timing analysis', evidence=evidence, verdict=Verdict.SUPPORTED)
    assert [x.id for x in _deduplicate_claims([a, b, c])] == ['a', 'c']

def test_wrong_vendor_claim_is_rejected_by_skill_guard():
    c = criterion('experience with Synopsys tools', cid='syn')
    parsed = ParsedRequest(role_title='Engineer', criteria=[c], search_variants=[])
    claim = Claim(id='wrong-vendor', candidate_id='p1', criterion_id='syn', text='Synopsys experience',
        evidence=[Evidence(record_type='person', record_id='p1', field_path='skills.professional_network_skills[0]', value='Innovus')],
        verdict=Verdict.SUPPORTED)
    result = _apply_skill_evidence_guard([claim], parsed, person(['Innovus']))
    assert result[0].verdict == Verdict.UNSUPPORTED

def test_seniority_criterion_is_scored_from_source_title():
    c = criterion('senior', category='seniority', priority=Priority.MUST, cid='sen')
    parsed = ParsedRequest(role_title='Senior Engineer', criteria=[c], search_variants=[])
    report = score_candidate('p1', 'Candidate', [], parsed, candidate_record=person(title='ASIC Physical Design Senior Engineer'))
    assert report.criterion_scores[0].met == 'yes'
    assert report.recommendation_status != 'needs_review'