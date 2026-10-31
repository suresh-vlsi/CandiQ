"""Gemini glue, built for tight free-tier quotas.

What it does to save calls:
  * disk cache: identical prompts are never paid for twice (.llm_cache/)
  * throttle: stays under GEMINI_RPM requests/minute (default 4)
  * fail fast: a *daily* quota error stops immediately instead of retrying
  * batch verify: ONE call verifies all of a candidate's claims

pip install google-genai pydantic
export GEMINI_API_KEY='...'
export GEMINI_MODEL='gemini-3.8-flash'   # whichever model your key can use
export GEMINI_RPM=4                      # set to your model's per-minute limit minus 1
"""
import hashlib
import json
import os
import re
import threading
import time
from datetime import date
from pathlib import Path

from pydantic import TypeAdapter

from prompts import (CLAIM_GEN_SYSTEM, PARSER_SYSTEM, VERIFIER_BATCH_SYSTEM,
                     VERIFIER_SYSTEM)
from schemas import Claim, ParsedRequest, Verdict

# Provider switch: set LLM_BASE_URL for ANY OpenAI-compatible API (Groq, OpenRouter,
# Cerebras, Mistral, Ollama...). Leave it unset to use Gemini.
BASE_URL = os.environ.get("LLM_BASE_URL")
if BASE_URL:
    MODEL = os.environ.get("LLM_MODEL", "")
else:
    MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

_client = None
_client_lock = threading.Lock()

def _get_client():
    """Create provider client only when a live LLM call is made (test-friendly)."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        if BASE_URL:
            if not MODEL:
                raise RuntimeError("Set LLM_MODEL when using LLM_BASE_URL")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the openai package for this provider") from exc
            _client = OpenAI(base_url=BASE_URL, api_key=os.environ.get("LLM_API_KEY", "none"))
        else:
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("Install google-genai to use Gemini") from exc
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY)")
            _client = genai.Client(api_key=api_key)
        return _client
RPM = float(os.environ.get("LLM_RPM") or os.environ.get("GEMINI_RPM", "4"))

CACHE = Path(".llm_cache")
CACHE.mkdir(exist_ok=True)

# Groq's OpenAI-compatible endpoint uses max_completion_tokens. For reasoning
# models, this budget can include both reasoning and visible output tokens.
MAX_COMPLETION_TOKENS = int(os.environ.get("LLM_MAX_COMPLETION_TOKENS", "8192"))


class QuotaExhausted(RuntimeError):
    """Daily quota is gone. Retrying will not help."""


_lock = threading.Lock()
_last_call = 0.0


def _throttle():
    global _last_call
    with _lock:
        wait = (60.0 / RPM) - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


class ResponseTruncated(RuntimeError):
    """The provider stopped generation before completing its response."""


def _generate(system: str, user: str, as_json: bool, retries: int = 3,
              max_completion_tokens: int | None = None) -> str:
    # Use a stage-specific output budget; include it in the cache key.
    token_budget = max_completion_tokens or MAX_COMPLETION_TOKENS
    key = hashlib.sha256(
        f"{MODEL}|{as_json}|{token_budget}|{system}|{user}".encode()
    ).hexdigest()
    cache_file = CACHE / f"{key}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    last = None
    for attempt in range(retries + 1):
        _throttle()
        try:
            client = _get_client()

            if BASE_URL:
                response = client.chat.completions.create(
                    model=MODEL,
                    temperature=0.2,
                    max_completion_tokens=token_budget,
                    reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "low"),
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )

                if not response.choices:
                    last = "provider returned no choices"
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                    continue

                choice = response.choices[0]
                if choice.finish_reason == "length":
                    raise ResponseTruncated(
                        f"{MODEL} reached the output-token limit "
                        f"({token_budget}); the response was truncated. "
                        "Increase LLM_MAX_COMPLETION_TOKENS if your model supports "
                        "a larger limit, or reduce the prompt/output size."
                    )

                raw_text = choice.message.content or ""
                text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.S).strip()

            else:
                from google.genai import types

                config = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.2,
                    response_mime_type="application/json" if as_json else "text/plain",
                )
                response = client.models.generate_content(
                    model=MODEL, contents=user, config=config
                )
                text = (response.text or "").strip()

            if text:
                cache_file.write_text(text, encoding="utf-8")
                return text

            last = "provider returned an empty response"

        except ResponseTruncated:
            # The same prompt and budget would likely truncate again. Let
            # call_json retry with an instruction to produce shorter JSON.
            raise
        except Exception as exc:
            msg = str(exc)
            last = msg

            if "PerDay" in msg or "per day" in msg.lower():
                raise QuotaExhausted(
                    f"Daily quota exhausted for {MODEL}. Check provider quota/"
                    "billing, use another key or model, or wait for reset."
                ) from exc

            retry_match = re.search(
                r"(?:retry|try again) in ([\d.]+)\s?s", msg, flags=re.I
            )
            if "429" in msg and retry_match:
                time.sleep(float(retry_match.group(1)) + 1)
                continue

        if attempt < retries:
            time.sleep(2 ** attempt)

    raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last}")


def _remove_markdown_json_fence(text: str) -> str:
    """Remove an optional Markdown JSON code fence."""
    cleaned = text.strip()
    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.I | re.S
    )
    return match.group(1).strip() if match else cleaned


def call_json(system: str, user: str, retries: int = 2,
              max_completion_tokens: int | None = None):
    last_err = None
    working_user = user

    for attempt in range(retries + 1):
        try:
            text = _generate(system, working_user, as_json=True,
                              max_completion_tokens=max_completion_tokens)
        except ResponseTruncated as exc:
            last_err = exc
            if attempt >= retries:
                raise ValueError(
                    f"LLM response remained truncated after {retries + 1} attempts. "
                    f"{exc}"
                ) from exc

            working_user += (
                "\n\nIMPORTANT: Your previous response was cut off because it "
                "was too long. Return a substantially shorter response while "
                "preserving all required fields. Output valid JSON only; do not "
                "use Markdown fences or explanations."
            )
            continue

        cleaned = _remove_markdown_json_fence(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            last_err = exc
            if attempt < retries:
                working_user += (
                    f"\n\nYour previous reply was not valid JSON "
                    f"(parser error: {exc}). Return a shorter, complete, valid "
                    "JSON response only. Do not use Markdown fences or explanations."
                )

    raise ValueError(
        f"LLM never returned valid JSON after {retries + 1} attempts: {last_err}"
    )


def generate_text(system: str, user: str) -> str:
    return _generate(system, user, as_json=False).strip()


# ---- Stage 1: parse ----
def parse_request(raw_request: str) -> ParsedRequest:
    return ParsedRequest.model_validate(call_json(
        PARSER_SYSTEM, raw_request,
        max_completion_tokens=int(os.getenv("LLM_PARSE_MAX_COMPLETION_TOKENS", "2048"))
    ))


# ---- Stage 4a: generate claims for one candidate (1 call) ----
def generate_claims(candidate: dict, criteria: list, companies: list) -> list[Claim]:
    user = json.dumps({
        "criteria": [c.model_dump(mode="json") for c in criteria],
        "candidate_record": candidate,
        "company_records": companies,
        "today": date.today().isoformat(),
    })
    raw_claims = call_json(
        CLAIM_GEN_SYSTEM, user,
        max_completion_tokens=int(os.getenv("LLM_CLAIM_MAX_COMPLETION_TOKENS", "1536"))
    )

    # `record_type` identifies the source record, not the field category.
    # Skills are fields inside the candidate/person record.
    for claim in raw_claims if isinstance(raw_claims, list) else []:
        for evidence in claim.get("evidence", []) if isinstance(claim, dict) else []:
            if evidence.get("record_type") == "skill":
                evidence["record_type"] = "person"

    return TypeAdapter(list[Claim]).validate_python(raw_claims)


# ---- Stage 4b: verify ----
def _resolve_field_path(record: dict, field_path: str):
    """Resolve dotted paths and numeric list indexes, e.g. a.b[2].c."""
    if not field_path or not isinstance(field_path, str):
        raise KeyError("empty field path")
    parts = re.findall(r"[^.\[\]]+", field_path)
    if not parts or ".".join(parts) == "": raise KeyError(field_path)
    current = record
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, (list, tuple)) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise KeyError(field_path)
    return current


def _quote_check(claim: Claim, records: dict[str, dict]) -> bool:
    """Require each quote to match the exact value at its cited field path."""
    if not claim.evidence:
        claim.verdict = Verdict.UNSUPPORTED
        claim.verifier_note = "Claim has no evidence citations."
        return False
    for ev in claim.evidence:
        record = records.get(ev.record_id)
        if record is None:
            claim.verdict = Verdict.UNSUPPORTED
            claim.verifier_note = f"Evidence record {ev.record_id!r} was not supplied."
            return False
        try:
            actual = _resolve_field_path(record, ev.field_path)
        except (KeyError, TypeError, IndexError):
            claim.verdict = Verdict.UNSUPPORTED
            claim.verifier_note = f"Cited field path {ev.field_path!r} does not exist in {ev.record_id}."
            return False
        # API values may be scalar, arrays, or objects. Evidence.value is a string;
        # compare to the exact scalar representation, never to the whole JSON blob.
        expected = actual if isinstance(actual, str) else json.dumps(actual, ensure_ascii=False, sort_keys=True) if isinstance(actual, (dict, list)) else str(actual)
        if ev.value != expected:
            claim.verdict = Verdict.UNSUPPORTED
            claim.verifier_note = f"Evidence quote does not exactly match {ev.field_path!r} in {ev.record_id}."
            return False
    return True

def verify_claims(claims: list[Claim], records: dict[str, dict]) -> list[Claim]:
    """Batch verify: programmatic check first, then ONE LLM call for the rest."""
    pending = [c for c in claims if _quote_check(c, records)]
    if not pending:
        return claims
    cited_ids = {ev.record_id for c in pending for ev in c.evidence}
    user = json.dumps({
        "today": date.today().isoformat(),
        "claims": [c.model_dump(mode="json") for c in pending],
        "sources": {rid: records[rid] for rid in cited_ids if rid in records},
    })
    out = call_json(
        VERIFIER_BATCH_SYSTEM, user,
        max_completion_tokens=int(os.getenv("LLM_VERIFY_MAX_COMPLETION_TOKENS", "2048"))
    )
    if not isinstance(out, list):
        for c in pending:
            c.verdict = Verdict.UNSUPPORTED
            c.verifier_note = "Verifier returned an invalid response format."
        return claims
    by_id = {str(o.get("id")): o for o in out if isinstance(o, dict) and o.get("id") is not None}
    for c in pending:
        o = by_id.get(str(c.id))
        if not o:
            c.verdict = Verdict.UNSUPPORTED
            c.verifier_note = "Verifier returned no verdict for this claim."
            continue
        try:
            c.verdict = Verdict(o["verdict"])
        except (KeyError, ValueError):
            c.verdict = Verdict.UNSUPPORTED
        c.verifier_note = o.get("note", "")
        c.corrected_text = o.get("corrected_text")
    return claims


def verify_all(claims: list[Claim], records: dict[str, dict]) -> list[Claim]:
    return verify_claims(claims, records)


def renderable(claims: list[Claim]) -> list[Claim]:
    return [c for c in claims if c.verified]


if __name__ == "__main__":
    parsed = parse_request("need a senior backend eng, BLR, ex-fintech, startup vibes")
    print(parsed.model_dump_json(indent=2))
