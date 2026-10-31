# Evidence-Based AI Recruitment Agent

A human-in-the-loop recruiting research assistant. It parses a hiring request, searches candidate profiles, enriches selected profiles, generates evidence-linked claims, verifies citations, and produces a Markdown shortlist. It does **not** contact candidates or make employment decisions.

## Architecture

1. Parse the request into atomic must-have / nice-to-have criteria.
2. Search Crustdata using strict, relaxed, and adjacent variants.
3. Deduplicate and pre-rank search results before enrichment.
4. Compute date-derived experience summaries deterministically.
5. Generate atomic claims with source field paths.
6. Validate every evidence citation against the exact cited field, then run independent LLM verification.
7. Score assessable criteria and report evidence coverage separately.
8. Write a Markdown report for recruiter review.

## Setup (Ubuntu / WSL)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY`. For live candidate search also set `CRUSTDATA_API_KEY`. Load environment variables before running:

```bash
set -a
source .env
set +a
```

Without `CRUSTDATA_API_KEY`, the pipeline uses invented mock candidates. Mock mode still requires a configured LLM provider to parse and verify claims.

## Run

```bash
python pipeline.py "Senior backend engineer in Bengaluru with Python and fintech experience" --top 8 --out shortlist.md
```

Optional outreach drafts are generated locally and are never sent:

```bash
python pipeline.py "Senior backend engineer" --top 8 --out shortlist.md --outreach
```

## Provider configuration

Gemini is the default. To use an OpenAI-compatible endpoint, set all three variables:

```bash
export LLM_BASE_URL="https://your-provider.example/v1"
export LLM_API_KEY="..."
export LLM_MODEL="provider-model-name"
```

Never commit `.env`, API keys, `.cache/`, `.llm_cache/`, virtual environments, or real candidate exports.

## Important scoring semantics

- `yes`, `partial`, `no`, and `unknown` are distinct.
- Unknown criteria are excluded from the match-score denominator; they are not silently treated as confirmed failures.
- `evidence_coverage` reports the weighted proportion of criteria that could be assessed.
- An unknown must-have or low evidence coverage results in `needs_review`.
- A verifier-confirmed contradiction on a must-have results in `not_recommended`.
- A high match score with low evidence coverage must not be interpreted as a hiring recommendation.
- Derived timeline anomalies are review prompts, not evidence of misconduct.

## Validation

```bash
python -m py_compile *.py
pytest -q
```

The test suite checks exact nested-field evidence validation, scoring semantics, and date-derived calculations without making API calls.

## Responsible use

Use job-related, consistently applied criteria. Do not use protected characteristics or proxies. Candidate data should be handled under applicable privacy, retention, and access-control requirements. Keep a qualified human recruiter responsible for decisions and verify important facts with candidates before acting on them.
