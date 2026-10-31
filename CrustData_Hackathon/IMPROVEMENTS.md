# Engineering improvements in this revision

## Implemented

- Exact evidence verification resolves the cited nested field path (including array indexes) and compares the quote with that field only. A matching string elsewhere in the JSON record no longer passes.
- Crustdata search follows `next_cursor` with a configurable page cap, validates response shape, deduplicates enrichment URLs, and handles cache corruption.
- API timeouts, retry delays, environment-based API version/base URL, and cache controls are configurable.
- Candidate scoring distinguishes verified mismatch from missing evidence. Unknown criteria are excluded from the score denominator and are reflected in weighted evidence coverage. Unknown must-have requirements trigger `needs_review`.
- Must-have contradictions trigger `not_recommended`; other candidates are labelled `strong_match`, `potential_match`, or `needs_review`.
- Timeline anomalies are worded as items to review, not conclusions about a candidate.
- Provider clients are initialized lazily, so pure scoring/evidence tests can run without API credentials or an installed provider SDK.
- Added `.gitignore`, `.env.example`, requirements, setup/run documentation, and automated tests.

## Deliberately not added yet

- No unverified frontend, interview automation, or extra agent layer. First validate the live Crustdata response schema and quotas; then build the UI around real response fields.
- No automatic hiring/rejection action and no automatic outreach sending.

## Live API validation still required

Crustdata's actual account permissions, response fields, pagination behavior, rate limits, and enrichment match payload must be checked with your API key. Search field names and API version are configurable, but should not be assumed correct until a real response is inspected.
