# Corrected Candidate Shortlist
**Role:** Senior ASIC Physical Design Engineer  
**Location:** Bengaluru, India  
**Assessment date:** 31 October 2026  
**Data source:** Crustdata-enriched profiles  
**Run completeness:** 5 searched · 5 enriched · 5 analysed · 28 claims generated · 6 rejected by verifier

## Executive summary

The recruitment pipeline completed the requested five-profile run. This corrected report reconciles the generated claims with the exact source evidence already present in the run report. No new LLM analysis or API call was performed.

| Rank | Candidate | Evidence-backed score | Assessment |
|---:|---|---:|---|
| 1 | Ramesha B | **92.9/100** | Strong match |
| 2 | Atish Dhoke | **78.6/100** | Potential match |
| 3= | Anup D | **71.4/100** | Potential match |
| 3= | Santhosh Begari | **71.4/100** | Potential match; verify timing skill source path |
| 5 | Lavanya Mittal | **64.3/100** | Potential match |

**Recommended screening order:** Ramesha B, Atish Dhoke, then Anup D and Santhosh Begari (tied), followed by Lavanya Mittal.

## What was corrected

1. **Atish Dhoke — wrong index and overgeneralised evidence.** The rejected claim cited skill index `[20]`, but the source report separately shows `skills.professional_network_skills[3] = "Primetime"`. The valid `[3]` entry supports Synopsys-tool and timing-analysis criteria. It does **not** support floorplanning, placement, or routing. Those three claims remain rejected/unknown.
2. **Santhosh Begari — terminology mismatch.** The verifier says the source wording is `"Static Timing Analysis"`, not the generic phrase `"timing analysis"`. These terms are semantically equivalent for the requested discipline, so the criterion is manually normalised to yes. The source report does not expose the exact skill-array path, so that path should be checked before final hiring decisions. The pipeline's original 71.4 score is retained and this manual normalization is disclosed.
3. **Ramesha B — vendor inference removed.** `"STA"` does not establish Synopsys tool experience. Synopsys remains unknown.
4. **No fabricated evidence.** No new source paths, skills, tools, or employment facts have been invented. Unknown remains unknown, not no.

## Scoring methodology

The report has eight criteria: three must-haves (ASIC physical-design experience, seniority, Bengaluru location) weighted 3 points each, and five nice-to-haves (Synopsys tools, timing analysis, floorplanning, placement, routing) weighted 1 point each. Maximum score = 14. Scores are calculated as earned points divided by 14. Unknown criteria receive no points until supported; this does not establish that the candidate lacks the skill.

| Candidate | Points | Score |
|---|---:|---:|
| Ramesha B | 13/14 | 92.9 |
| Atish Dhoke | 11/14 | 78.6 |
| Anup D | 10/14 | 71.4 |
| Santhosh Begari | 10/14 | 71.4 |
| Lavanya Mittal | 9/14 | 64.3 |

## Candidate assessments

### 1. Ramesha B — 92.9/100
**Assessment:** Strong match  
**Source record ID:** `38432919`

| Criterion | Priority | Result | Evidence / interpretation |
|---|---|---|---|
| ASIC physical-design experience | Must-have | Yes | Current title: Senior Engineer 1 Asic physical design; prior ASIC physical-design titles. |
| Synopsys tools | Nice-to-have | Unknown | STA is a discipline, not proof of Synopsys vendor/tool use. |
| Timing analysis | Nice-to-have | Yes | Skills: Timing Closure; STA. |
| Floorplanning | Nice-to-have | Yes | Skills: Floorplanning; Floor Plans. |
| Placement | Nice-to-have | Yes | Skill: Place & Route. |
| Routing | Nice-to-have | Yes | Skill: Place & Route. |
| Seniority | Must-have | Yes | Current title and headline contain Senior. |
| Bengaluru, India | Must-have | Yes | Profile location: Bengaluru, Karnataka, India. |

**Reconciliation note:** One rejected claim attempted to infer Synopsys tools from STA. It remains unknown and is not counted.

### 2. Atish Dhoke — 78.6/100
**Assessment:** Potential match  
**Source record ID:** `183131547`

| Criterion | Priority | Result | Evidence / interpretation |
|---|---|---|---|
| ASIC physical-design experience | Must-have | Yes | Current title: Senior ASIC Physical Design Engineer. |
| Synopsys tools | Nice-to-have | Yes | Exact profile skill at skills.professional_network_skills[3]: Primetime. |
| Timing analysis | Nice-to-have | Yes | PrimeTime is direct timing-analysis tool evidence. |
| Floorplanning | Nice-to-have | Unknown | PrimeTime does not establish floorplanning. |
| Placement | Nice-to-have | Unknown | PrimeTime does not establish placement. |
| Routing | Nice-to-have | Unknown | PrimeTime does not establish routing. |
| Seniority | Must-have | Yes | Current title explicitly contains Senior. |
| Bengaluru, India | Must-have | Yes | Profile location: Bengaluru, Karnataka, India. |

**Reconciliation note:** Four generated claims were rejected: one cited the wrong skill index [20], while the valid source entry is [3]; three incorrectly reused PrimeTime as evidence for floorplanning, placement, and routing. The valid [3] entry independently supports Synopsys and timing-analysis criteria. Derived profile data flags an approximately 38-month employment gap (Dec 2017–Feb 2021); verify respectfully during screening.

### 3. Anup D — 71.4/100
**Assessment:** Potential match  
**Source record ID:** `57356570`

| Criterion | Priority | Result | Evidence / interpretation |
|---|---|---|---|
| ASIC physical-design experience | Must-have | Yes | Skill: Physical Design; current title: Senior ASIC Physical design engineer. |
| Synopsys tools | Nice-to-have | Unknown | No qualifying tool evidence shown. |
| Timing analysis | Nice-to-have | Unknown | No qualifying evidence shown. |
| Floorplanning | Nice-to-have | Yes | Skill: Floorplanning. |
| Placement | Nice-to-have | Unknown | No qualifying evidence shown. |
| Routing | Nice-to-have | Unknown | No qualifying evidence shown. |
| Seniority | Must-have | Yes | Current title explicitly contains Senior. |
| Bengaluru, India | Must-have | Yes | Profile location: Bengaluru, Karnataka, India. |

**Reconciliation note:** No rejected claims were listed for this candidate in the source report.

### 4. Santhosh Begari — 71.4/100
**Assessment:** Potential match — timing evidence needs confirmation  
**Source record ID:** `61439397`

| Criterion | Priority | Result | Evidence / interpretation |
|---|---|---|---|
| ASIC physical-design experience | Must-have | Yes | Prior title: ASIC Physical Design Engineer at Einfochips. |
| Synopsys tools | Nice-to-have | Unknown | No qualifying tool evidence shown. |
| Timing analysis | Nice-to-have | Yes — manual normalization | Verifier rejection states source wording is Static Timing Analysis. This is semantically equivalent to the requested timing-analysis criterion; the exact source field path was not printed in the report. |
| Floorplanning | Nice-to-have | Unknown | No qualifying evidence shown. |
| Placement | Nice-to-have | Unknown | No qualifying evidence shown. |
| Routing | Nice-to-have | Unknown | No qualifying evidence shown. |
| Seniority | Must-have | Yes | Current title: Senior Physical Design Engineer; 3nm/5nm; RTL-to-GDS. |
| Bengaluru, India | Must-have | Yes | Profile location: Bengaluru, Karnataka, India. |

**Reconciliation note:** One generated timing-analysis claim was rejected because its wording did not exactly match the source phrase Static Timing Analysis. For this corrected report, the source phrase is manually normalized to the requested timing-analysis criterion; the original 71.4 score is retained. Confirm the exact skill-array entry in the source profile before relying on this point.

### 5. Lavanya Mittal — 64.3/100
**Assessment:** Potential match  
**Source record ID:** `155901549`

| Criterion | Priority | Result | Evidence / interpretation |
|---|---|---|---|
| ASIC physical-design experience | Must-have | Yes | Current employment title: ASIC Physical Design Senior Engineer. |
| Synopsys tools | Nice-to-have | Unknown | No qualifying tool evidence shown. |
| Timing analysis | Nice-to-have | Unknown | No qualifying evidence shown. |
| Floorplanning | Nice-to-have | Unknown | No qualifying evidence shown. |
| Placement | Nice-to-have | Unknown | No qualifying evidence shown. |
| Routing | Nice-to-have | Unknown | No qualifying evidence shown. |
| Seniority | Must-have | Yes | Current title explicitly contains Senior. |
| Bengaluru, India | Must-have | Yes | Profile location: Bengaluru, Karnataka, India. |

**Reconciliation note:** No rejected claims were listed for this candidate in the source report.

## Structured technical-screen checklist

1. Confirm current employment, role, Bengaluru location, notice period, and availability.
2. Ask candidates to name the exact EDA tools used (for example, PrimeTime, Design Compiler, IC Compiler II, Innovus, or Tempus) and explain their individual responsibilities.
3. Probe timing analysis: constraints, setup/hold closure, timing reports, timing closure, and sign-off ownership.
4. Probe floorplanning, placement, clock-tree synthesis, routing, and physical verification separately. Do not infer one from another.
5. Ask for project context (process node, block complexity, ownership, and measurable outcomes) without requesting confidential employer information.
6. Verify employment dates and clarify apparent gaps respectfully.

## Final recommendation

Prioritise Ramesha B for the first technical screen. Atish Dhoke is the next candidate to screen: the corrected source interpretation recognises PrimeTime at skill index `[3]` for Synopsys and timing-analysis experience, while leaving floorplanning, placement, and routing unknown. Anup D and Santhosh Begari are tied at 71.4; confirm Santhosh's exact Static Timing Analysis skill-array path. Keep Lavanya Mittal in the shortlist.

These scores are evidence-coverage scores against the stated criteria, not probabilities of job performance. Unknown nice-to-have skills are not disqualifying. Validate all claims in structured interviews and with candidate confirmation.

---
*Prepared by reconciling the Crustdata-enriched source report and verifier notes from the completed run. No LLM calls were rerun for this corrected deliverable.*
