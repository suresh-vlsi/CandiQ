"""End-to-end recruiter agent.

Usage:
    python pipeline.py "need a senior backend eng in Bangalore, ex-fintech" [--top 10] [--out report.md]

Flow: parse -> search (strict -> relaxed -> adjacent until enough) -> enrich
      -> claims -> verify -> score -> markdown report. Never contacts anyone.
"""
import argparse
import re
from datetime import date
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import os

# Real Crustdata when a key is set, otherwise the built-in mock candidates.
USE_MOCK = os.environ.get("USE_MOCK_DATA") == "1" or not os.environ.get("CRUSTDATA_API_KEY")
if USE_MOCK:
    from mock_data import (CrustdataError, enrich_people, profile_url,
                           search_people, variant_to_filters)
else:
    from crustdata import (CrustdataError, enrich_people, profile_url,
                           search_people, variant_to_filters)
from derived import compute_derived
from llm import QuotaExhausted, generate_claims, generate_text, parse_request, verify_all
from schemas import (CandidateReport, Claim, Criterion, CriterionScore, ParsedRequest,
                     Priority, Verdict)

MIN_CANDIDATES = int(os.getenv("MIN_CANDIDATES", "12"))
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "25"))
MAX_SEARCH_PAGES = int(os.getenv("MAX_SEARCH_PAGES", "3"))
ENRICH_BUFFER = int(os.getenv("ENRICH_BUFFER", "2"))
WEIGHTS = {Priority.MUST: 3.0, Priority.NICE: 1.0}
CREDIT = {"yes": 1.0, "partial": 0.5, "no": 0.0, "unknown": 0.0}


def log(msg: str):
    print(f"[agent] {msg}", file=sys.stderr)


# ------------------------------------------------------------ stage 2: search

def _requested_city(parsed: ParsedRequest) -> str | None:
    """Return a requested city from a location criterion, if one is explicit."""
    for criterion in parsed.criteria:
        if getattr(criterion, "category", None) == "location":
            parts = [p.strip() for p in criterion.text.split(",") if p.strip()]
            if len(parts) >= 2:
                return parts[0]
            if len(parts) == 1:
                token = _normalise_location(parts[0])
                known_countries = {
                    "india", "united states", "usa", "united kingdom", "uk",
                    "canada", "singapore", "germany", "australia",
                }
                if token not in known_countries:
                    return parts[0]
    return None


def _profile_location_status(profile: dict, requested_city: str | None) -> str:
    """Return match/mismatch/unknown using search-result location fields."""
    if not requested_city:
        return "unknown"
    bp = profile.get("basic_profile") or {}
    location = bp.get("location") or {}
    if not isinstance(location, dict):
        return "unknown"
    actual = str(location.get("city") or "").strip()
    if not actual:
        raw = str(location.get("raw") or location.get("full_location") or "")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        actual = parts[0] if parts else ""
    if not actual:
        return "unknown"
    return (
        "match"
        if _normalise_location(actual) == _normalise_location(requested_city)
        else "mismatch"
    )


def gather_candidates(parsed: ParsedRequest) -> dict[str, dict]:
    """Returns {rid: {"url":..., "variant":...}} deduped by crustdata_person_id."""
    found: dict[str, dict] = {}
    requested_city = _requested_city(parsed)
    for variant in parsed.search_variants:
        filters = variant_to_filters(variant)
        if not filters:
            log(f"variant '{variant.name}' has no usable filters, skipping")
            continue
        if os.getenv("CRUSTDATA_DEBUG", "0") == "1":
            log(
                f"[DEBUG] Searching variant={variant.name!r} "
                f"with filters={json.dumps(filters, ensure_ascii=False)}"
            )
        try:
            profiles = search_people(filters, limit=SEARCH_LIMIT, max_pages=MAX_SEARCH_PAGES)
        except CrustdataError as e:
            # If the optional city field/operator is unsupported by this
            # Crustdata account/API version, retry once with the known-working
            # country-only filter. The pipeline still applies local city
            # matching before deciding which profiles to enrich.
            if os.getenv("CRUSTDATA_CITY_FILTER", "0") == "1":
                log(
                    f"variant '{variant.name}' city filter failed; "
                    f"retrying country-only discovery: {e}"
                )
                previous = os.environ.get("CRUSTDATA_CITY_FILTER")
                os.environ["CRUSTDATA_CITY_FILTER"] = "0"
                try:
                    fallback_filters = variant_to_filters(variant)
                    profiles = search_people(
                        fallback_filters,
                        limit=SEARCH_LIMIT,
                        max_pages=MAX_SEARCH_PAGES,
                    )
                except CrustdataError as fallback_error:
                    log(f"variant '{variant.name}' fallback failed: {fallback_error}")
                    continue
                finally:
                    if previous is None:
                        os.environ.pop("CRUSTDATA_CITY_FILTER", None)
                    else:
                        os.environ["CRUSTDATA_CITY_FILTER"] = previous
            else:
                log(f"variant '{variant.name}' failed: {e}")
                continue
        added = 0
        for p in profiles:
            if os.getenv("CRUSTDATA_DEBUG", "0") == "1":
                bp_debug = p.get("basic_profile") or {}
                loc_debug = bp_debug.get("location") or {}
                if not isinstance(loc_debug, dict):
                    loc_debug = {"value": str(loc_debug)}
                log(
                    "[DEBUG] Returned profile location: "
                    f"city={loc_debug.get('city')!r}, "
                    f"country={loc_debug.get('country')!r}, "
                    f"raw={loc_debug.get('raw')!r}, "
                    f"full_location={loc_debug.get('full_location')!r}"
                )
            rid, url = str(p.get("crustdata_person_id")), profile_url(p)
            if rid != "None" and url and rid not in found:
                found[rid] = {
                    "url": url,
                    "variant": variant.name,
                    "profile": p,
                    "location_status": _profile_location_status(p, requested_city),
                }
                if os.getenv("CRUSTDATA_DEBUG", "0") == "1":
                    log(
                        f"[DEBUG] Candidate {rid} local location status="
                        f"{found[rid]['location_status']} for requested city "
                        f"{requested_city!r}"
                    )
                added += 1
        log(f"variant '{variant.name}': {len(profiles)} results, {added} new")
        if len(found) >= MIN_CANDIDATES:
            break
    return found


# ------------------------------------------------------------ pre-ranking (no LLM, no credits)

def _blob(profile: dict) -> str:
    bp = profile.get("basic_profile", {})
    parts = [bp.get("headline", ""), bp.get("current_title", ""),
             (bp.get("location") or {}).get("raw", "")]
    ed = profile.get("experience", {}).get("employment_details", {})
    for j in (ed.get("current") or []) + (ed.get("past") or []):
        parts += [j.get("name", ""), j.get("title", "")]
    return " ".join(parts).lower()


def _frac(phrase: str, blob: str) -> float:
    """Fraction of the phrase's words present in the blob."""
    words = [w for w in re.findall(r"\w+", phrase.lower()) if len(w) > 2]
    return sum(w in blob for w in words) / len(words) if words else 0.0


def prerank(profile: dict, parsed: ParsedRequest, variant_name: str) -> float:
    """Cheap relevance score from search results, so LLM calls and enrich
    credits go to the most promising candidates instead of the first few."""
    strict = next((v for v in parsed.search_variants if v.name == "strict"),
                  parsed.search_variants[0])
    blob = _blob(profile)
    score = 3 * max((_frac(t, blob) for t in strict.titles), default=0)
    score += 2 * max((_frac(l, blob) for l in strict.locations), default=0)
    score += 0.5 * sum(_frac(k, blob) for k in strict.skills)
    score += 1 if variant_name == "strict" else 0
    return score


# ------------------------------------------------------------ stage 3-4: per candidate

def _compact_person_for_claims(record: dict, criteria: list) -> dict:
    """Keep claim-relevant fields while preserving original evidence paths."""
    bp = record.get("basic_profile") or {}
    location = bp.get("location") or {}
    basic = {
        key: bp[key] for key in ("name", "headline", "current_title")
        if key in bp and bp[key] not in (None, "", [])
    }
    if location:
        basic["location"] = {
            key: location[key] for key in ("raw", "full_location", "country", "city")
            if key in location and location[key] not in (None, "", [])
        }

    exp = record.get("experience") or {}
    employment = exp.get("employment_details") or {}
    compact_employment = {}
    keep_job_fields = (
        "name", "title", "start_date", "end_date",
        "company_industry", "company_headcount_latest"
    )
    for bucket in ("current", "past"):
        jobs = employment.get(bucket)
        if isinstance(jobs, list):
            # Keep newest entries only; prefix slicing preserves original indexes.
            compact_employment[bucket] = [
                {k: job[k] for k in keep_job_fields
                 if k in job and job[k] not in (None, "", [])}
                if isinstance(job, dict) else job
                for job in jobs[:10]
            ]

    # Keep a bounded prefix of skills; original array indexes remain valid.
    skill_data = record.get("skills") or {}
    raw_skills = skill_data.get("professional_network_skills") or []
    compact_skills = raw_skills[:40]

    derived = record.get("derived") or {}
    compact_derived = {
        key: derived[key] for key in ("total_experience", "role_durations", "red_flags")
        if key in derived
    }
    compact = {
        "record_id": record.get("record_id"),
        "basic_profile": basic,
        "experience": {"employment_details": compact_employment},
        "skills": {"professional_network_skills": compact_skills},
        "derived": compact_derived,
    }

    if any(getattr(c, "category", None) == "education" for c in criteria):
        if "education" in record:
            compact["education"] = record["education"]
    return compact


def process_candidate(rid: str, person_data: dict, parsed: ParsedRequest):
    """Generate claims from a compact view; verify against the full record."""
    record = {"record_id": rid, **person_data,
              "derived": compute_derived(person_data, date.today())}
    records = {rid: record}
    claim_record = _compact_person_for_claims(record, parsed.criteria)
    claims = generate_claims(claim_record, parsed.criteria, companies=[])
    for c in claims:
        c.candidate_id = rid
    claims = _deduplicate_claims(claims)
    verified = verify_all(claims, records)
    return _apply_skill_evidence_guard(verified, parsed, record)


# ------------------------------------------------------------ stage 5: score + render

def _normalise_location(value: str) -> str:
    """Normalise common city aliases for deterministic location comparison."""
    value = re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())
    value = " ".join(value.split())
    aliases = {
        "bangalore": "bengaluru",
        "bengaluru urban": "bengaluru",
        "gurgaon": "gurugram",
        "bombay": "mumbai",
        "madras": "chennai",
        "calcutta": "kolkata",
    }
    return aliases.get(value, value)


def _location_criterion_result(criterion: Criterion, candidate_record: dict | None) -> str:
    """Compare requested location with structured source location.

    Returns yes/no/unknown. A country match alone cannot satisfy a city-level
    requirement. A mismatch means current location does not meet the stated
    location filter; relocation/remote-work willingness is not inferred.
    """
    if not candidate_record:
        return "unknown"

    location = (candidate_record.get("basic_profile") or {}).get("location") or {}
    if not isinstance(location, dict):
        location = {"raw": str(location)}

    raw = str(location.get("raw") or location.get("full_location") or "")
    actual_city = str(location.get("city") or "").strip()
    actual_country = str(location.get("country") or "").strip()
    raw_parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not actual_city and raw_parts:
        actual_city = raw_parts[0]
    if not actual_country and raw_parts:
        actual_country = raw_parts[-1]

    requested_parts = [part.strip() for part in criterion.text.split(",") if part.strip()]
    expected_city = requested_parts[0] if len(requested_parts) >= 2 else ""
    expected_country = requested_parts[-1] if len(requested_parts) >= 2 else ""

    if len(requested_parts) == 1:
        token = _normalise_location(requested_parts[0])
        if token in {"india", "united states", "usa", "united kingdom", "uk",
                     "canada", "singapore", "germany", "australia"}:
            expected_country = requested_parts[0]
        else:
            expected_city = requested_parts[0]

    if expected_city:
        if not actual_city:
            return "unknown"
        if _normalise_location(actual_city) != _normalise_location(expected_city):
            return "no"

    if expected_country:
        if not actual_country:
            return "unknown"
        if _normalise_location(actual_country) != _normalise_location(expected_country):
            return "no"

    return "yes" if (expected_city or expected_country) else "unknown"


_SYNOPYS_TOOLS = {
    "primetime", "prime time", "design compiler", "ic compiler",
    "ic compiler ii", "fusion compiler", "formality", "vcs", "verdi",
    "starrc", "hspice", "spyglass", "tetramax", "dftmax",
}

def _normalise_skill(value: str) -> str:
    value = str(value or "").casefold().replace("®", "").replace("™", "")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())

def _candidate_skills(record: dict | None) -> list[str]:
    if not isinstance(record, dict): return []
    raw = ((record.get("skills") or {}).get("professional_network_skills") or [])
    return [str(x) for x in raw if isinstance(x, str) and x.strip()]

def _contains_any_skill(skills: list[str], terms: set[str]) -> bool:
    normalized = [_normalise_skill(x) for x in skills]
    normalized_terms = {_normalise_skill(x) for x in terms}
    return any(item == term or (len(term) > 3 and term in item)
               for item in normalized for term in normalized_terms)

def _skill_taxonomy(criterion: Criterion) -> str | None:
    text = _normalise_skill(criterion.text)
    if "synopsys" in text: return "synopsys"
    words = set(text.split())
    if any(x in text for x in ("timing analysis", "static timing", "timing closure")) or "sta" in words: return "timing"
    if "floorplan" in text or "floor plan" in text: return "floorplanning"
    if "placement" in text: return "placement"
    if "routing" in text or " route " in f" {text} ": return "routing"
    return None

def _deterministic_skill_result(criterion: Criterion, record: dict | None) -> str | None:
    """Return yes/unknown for mapped skills; None delegates to verified claims."""
    taxonomy = _skill_taxonomy(criterion)
    if taxonomy is None: return None
    skills = _candidate_skills(record)
    terms = {
        "synopsys": _SYNOPYS_TOOLS,
        "timing": {"sta", "static timing analysis", "timing analysis", "timing closure", "primetime", "prime time", "tempus"},
        "floorplanning": {"floorplanning", "floor plan", "floor plans"},
        "placement": {"placement", "place and route", "place route", "pnr"},
        "routing": {"routing", "route", "place and route", "place route", "pnr"},
    }[taxonomy]
    return "yes" if _contains_any_skill(skills, terms) else "unknown"

def _apply_skill_evidence_guard(claims: list[Claim], parsed: ParsedRequest, candidate_record: dict | None) -> list[Claim]:
    """Reject semantically mismatched skill claims even when their quotes exist."""
    skills = _candidate_skills(candidate_record)
    for criterion in parsed.criteria:
        if criterion.category != "skill" or _skill_taxonomy(criterion) is None: continue
        for claim in claims:
            if claim.criterion_id != criterion.id or not claim.verified: continue
            cited = [e.value for e in claim.evidence if e.record_type == 'person' and e.field_path.startswith('skills.professional_network_skills[')]
            exact = [value for value in cited if value in skills]
            single_record = {'skills': {'professional_network_skills': exact}}
            if not exact or _deterministic_skill_result(criterion, single_record) != 'yes':
                claim.verdict = Verdict.UNSUPPORTED
                claim.verifier_note = f'The cited skill does not establish {_skill_taxonomy(criterion)} experience under the deterministic skill taxonomy.'
                claim.corrected_text = None
    return claims

def _seniority_result(criterion: Criterion, record: dict | None) -> str | None:
    """Recognise explicit seniority in source titles/headlines."""
    if criterion.category != "seniority" or "senior" not in _normalise_skill(criterion.text): return None
    if not isinstance(record, dict): return 'unknown'
    bp = record.get('basic_profile') or {}
    titles = [bp.get('current_title', ''), bp.get('headline', '')]
    employment = (record.get('experience') or {}).get('employment_details') or {}
    for bucket in ('current', 'past'):
        for job in employment.get(bucket) or []:
            if isinstance(job, dict): titles.append(job.get('title', ''))
    source = ' | '.join(_normalise_skill(x) for x in titles if x)
    if re.search(r'\b(senior|principal|staff|lead|director|distinguished)\b', source): return 'yes'
    if re.search(r'\b(junior|intern|internship|graduate|entry level)\b', source): return 'no'
    return 'unknown'

def _deduplicate_claims(claims: list[Claim]) -> list[Claim]:
    """Drop exact duplicates but retain distinct criterion links."""
    result, seen = [], set()
    for claim in claims:
        ev_key = tuple(sorted((e.record_type, e.record_id, e.field_path, e.value) for e in claim.evidence))
        key = (claim.criterion_id, _normalise_skill(claim.text), ev_key)
        if key not in seen: seen.add(key); result.append(claim)
    return result

def score_candidate(rid: str, name: str, claims: list[Claim], parsed: ParsedRequest,
                    candidate_record: dict | None = None) -> CandidateReport:
    """Calculate an evidence-backed match score and evidence coverage separately.

    The score denominator includes ALL criterion weights. Unknown criteria earn
    no points because they are not yet evidenced, but unknown is never treated
    as proof that the candidate lacks the skill. Evidence coverage reports the
    weighted share of criteria that could be assessed. Unknown must-haves
    trigger human review; only verifier-confirmed contradictions count as a
    confirmed failure.
    """
    scores, earned, assessable_weight, total_weight = [], 0.0, 0.0, 0.0
    must_no, must_unknown = False, False
    for crit in parsed.criteria:
        mine = [c for c in claims if c.criterion_id == crit.id]
        if crit.category == "location":
            met = _location_criterion_result(crit, candidate_record)
        elif candidate_record is not None and crit.category == "seniority" and _seniority_result(crit, candidate_record) is not None:
            met = _seniority_result(crit, candidate_record)
        elif candidate_record is not None and crit.category == "skill" and _deterministic_skill_result(crit, candidate_record) is not None:
            met = _deterministic_skill_result(crit, candidate_record)
        elif any(c.verdict == Verdict.SUPPORTED for c in mine): met = "yes"
        elif any(c.verdict == Verdict.PARTIAL for c in mine): met = "partial"
        elif any(c.verdict == Verdict.CONTRADICTED for c in mine): met = "no"
        else: met = "unknown"
        weight = WEIGHTS[crit.priority]
        total_weight += weight
        if met != "unknown":
            assessable_weight += weight
        # Unknown earns zero in the evidence-backed match score, but remains
        # explicitly "unknown" in the criterion table and is not a rejection.
        earned += weight * CREDIT[met]
        if crit.priority == Priority.MUST and met == "no": must_no = True
        if crit.priority == Priority.MUST and met == "unknown": must_unknown = True
        scores.append(CriterionScore(criterion_id=crit.id, met=met,
                                     claim_ids=[c.id for c in mine if c.verified]))
    # Use the full requested-criteria weight as denominator. This prevents a
    # candidate with only a few verified positives from receiving an artificial
    # 100/100. Unknowns lower the evidence-backed score but not eligibility.
    score = 100 * earned / total_weight if total_weight else 0.0
    coverage = 100 * assessable_weight / total_weight if total_weight else 0.0
    if must_no: status = "not_recommended"
    elif must_unknown or coverage < 60: status = "needs_review"
    elif score >= 80: status = "strong_match"
    else: status = "potential_match"
    return CandidateReport(candidate_id=rid, name=name, score=round(score, 1),
                           evidence_coverage=round(coverage, 1), recommendation_status=status,
                           criterion_scores=scores, claims=claims)


def draft_outreach(report: CandidateReport, role: str) -> str:
    """DRAFT ONLY. Uses verified claims only. Never sent anywhere."""
    facts = [c.corrected_text or c.text for c in report.claims if c.verified][:3]
    return generate_text(
        "Write a short, warm recruiter outreach message (under 90 words). "
        "Use ONLY the facts given. No flattery beyond them. No invented details.",
        f"Role: {role}\nCandidate: {report.name}\nFacts:\n- " + "\n- ".join(facts))


def render(parsed: ParsedRequest, reports: list[CandidateReport], meta: dict) -> str:
    crit = {c.id: c for c in parsed.criteria}
    L = [f"# Shortlist: {parsed.role_title}", ""]
    if parsed.assumptions:
        L += ["**Assumptions made:**"] + [f"- {a}" for a in parsed.assumptions] + [""]
    if parsed.conflicts:
        L += ["**Conflicts in the request:**"] + [f"- {a}" for a in parsed.conflicts] + [""]
    L += [f"_Searched {meta['found']} candidates, enriched {meta['enriched']}, analysed the best "
          f"{meta['analysed']}, generated {meta['claims']} claims, "
          f"**{meta['rejected']} rejected by the verifier**. The evidence-backed match score uses "
          f"the weight of ALL requested criteria; unknown criteria earn no points until verified, "
          f"but are not evidence that a candidate lacks the skill. Evidence coverage is the weighted "
          f"share of criteria assessed. Unknown must-have criteria require human review. "
          f"Experience figures are computed by code from record dates._", ""]
    for i, r in enumerate(reports, 1):
        L += [f"## {i}. {r.name} ({r.score}/100 evidence-backed match)", "", f"**Status:** `{r.recommendation_status}` · **Evidence coverage:** {r.evidence_coverage}%", ""]
        L += ["| Criterion | Priority | Met |", "|---|---|---|"]
        for s in r.criterion_scores:
            c = crit[s.criterion_id]
            L.append(f"| {c.text} | {c.priority.value} | {s.met} |")
        L += ["", "**Evidence**"]
        for c in r.claims:
            if c.verified:
                ev = "; ".join(f"`{e.record_id}:{e.field_path}` = {e.value!r}" for e in c.evidence)
                changed = bool(c.corrected_text) and c.corrected_text.strip() != c.text.strip()
                tag = (" _(corrected)_" if changed
                       else " _(partially supported)_" if c.verdict == Verdict.PARTIAL else "")
                L.append(f"- {c.corrected_text or c.text}{tag}  \n  <sub>{ev}</sub>")
        flags = [c for c in r.claims if c.criterion_id is None and c.verified]
        if flags:
            L += ["", "**Red flags**"] + [f"- {c.corrected_text or c.text}" for c in flags]
        rej = [c for c in r.claims if not c.verified]
        if rej:
            L += ["", "<details><summary>Rejected claims</summary>", ""]
            L += [f"- ~~{c.text}~~ ({c.verdict.value}: {c.verifier_note})" for c in rej]
            L += ["", "</details>"]
        if r.outreach_draft:
            L += ["", "**Outreach draft (not sent)**", "", f"> {r.outreach_draft}"]
        L.append("")
    return "\n".join(L)


# ------------------------------------------------------------ main

def run(request: str, top: int = 10, out: str = "report.md", outreach: bool = False):
    log("data source: " + ("MOCK candidates (no Crustdata key)" if USE_MOCK else "Crustdata API"))
    log("parsing request")
    if top < 1:
        raise ValueError("--top must be at least 1")
    parsed = parse_request(request)
    if not parsed.criteria or not parsed.search_variants:
        msg = "The request did not produce usable hiring criteria or search variants. Please provide a role and requirements."
        log(msg)
        open(out, "w", encoding="utf-8").write(f"# {parsed.role_title or 'Recruitment request'}\n\n{msg}\n")
        return
    log(f"{len(parsed.criteria)} criteria, {len(parsed.search_variants)} variants")

    found = gather_candidates(parsed)
    if not found:
        msg = "No candidates found even after loosening filters. Try a broader request."
        log(msg)
        open(out, "w", encoding="utf-8").write(f"# {parsed.role_title}\n\n{msg}\n")
        return

    # rank by search-result relevance, enrich the best (a couple extra: some will not match)
    ranked = sorted(
        found.values(),
        key=lambda v: (
            {"match": 2, "unknown": 1, "mismatch": 0}.get(v.get("location_status"), 1),
            prerank(v["profile"], parsed, v["variant"]),
        ),
        reverse=True,
    )
    requested_city = _requested_city(parsed)
    if requested_city:
        n_city_matches = sum(1 for v in ranked if v.get("location_status") == "match")
        log(
            f"location pre-filter: {n_city_matches} confirmed {requested_city} matches, "
            f"{sum(1 for v in ranked if v.get('location_status') == 'unknown')} unknown, "
            f"{sum(1 for v in ranked if v.get('location_status') == 'mismatch')} mismatches"
        )
    # Do not spend enrichment/LLM credits on candidates whose known city
    # conflicts with an explicit city requirement. Keep unknown locations for
    # review; they may be missing city data in the search response.
    if requested_city:
        eligible_ranked = [
            v for v in ranked if v.get("location_status") != "mismatch"
        ]
        excluded = len(ranked) - len(eligible_ranked)
        if excluded:
            log(
                f"excluded {excluded} candidates with confirmed location "
                f"mismatch against {requested_city} before enrichment"
            )
        ranked = eligible_ranked
        if not ranked:
            msg = (
                f"No candidates with a confirmed or unknown location remained "
                f"for the requested city: {requested_city}. "
                f"Searched {len(found)} profiles; all had a confirmed different city. "
                "Broaden the location requirement or rerun after checking the "
                "Crustdata city filter configuration."
            )
            log(msg)
            open(out, "w", encoding="utf-8").write(
                f"# {parsed.role_title}\n\n{msg}\n"
            )
            return

    urls = [v["url"] for v in ranked[: top + ENRICH_BUFFER]]
    log(f"pre-ranked {len(found)} candidates, enriching the best {len(urls)}")
    enriched = enrich_people(urls)
    url_to_rid = {v["url"]: rid for rid, v in found.items()}

    people = {}
    for url, pdata in enriched.items():
        rid = url_to_rid.get(url)
        if rid and pdata:
            people[rid] = pdata
    log(f"{len(people)} profiles enriched successfully")
    n_enriched = len(people)
    people = dict(list(people.items())[:top])      # LLM quota is tight: process only `top`
    log(f"processing {len(people)} candidates")

    def work(item):
        rid, pdata = item
        try:
            claims = process_candidate(rid, pdata, parsed)
            name = pdata.get("basic_profile", {}).get("name", rid)
            return score_candidate(rid, name, claims, parsed, candidate_record=pdata)
        except QuotaExhausted as e:
            log(f"STOPPING candidate {rid}: {e}")
            return None
        except Exception as e:           # one bad candidate must not kill the run
            log(f"candidate {rid} failed: {e}")
            return None

    # One candidate at a time: avoids concurrent bursts against Groq TPM limits.
    with ThreadPoolExecutor(max_workers=1) as pool:
        reports = [r for r in pool.map(work, people.items()) if r]

    if not reports:
        msg = "No candidate could be processed (LLM errors or quota). See the log."
        log(msg)
        open(out, "w", encoding="utf-8").write(f"# {parsed.role_title}\n\n{msg}\n")
        return
    status_rank = {
        "strong_match": 3,
        "potential_match": 2,
        "needs_review": 1,
        "not_recommended": 0,
    }
    reports.sort(
        key=lambda r: (status_rank.get(r.recommendation_status, 0),
                       r.score, r.evidence_coverage),
        reverse=True,
    )
    reports = reports[:top]
    if outreach:
        for r in reports[:3]:
            r.outreach_draft = draft_outreach(r, parsed.role_title)

    all_claims = [c for r in reports for c in r.claims]
    meta = {"found": len(found), "enriched": n_enriched, "analysed": len(reports), "claims": len(all_claims),
            "rejected": sum(1 for c in all_claims if not c.verified)}
    open(out, "w", encoding="utf-8").write(render(parsed, reports, meta))
    log(f"wrote {out}  {json.dumps(meta)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default="report.md")
    ap.add_argument("--outreach", action="store_true")
    a = ap.parse_args()
    run(a.request, a.top, a.out, a.outreach)
