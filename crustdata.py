"""Crustdata Person Search + Enrichment client.

Credentials are read from CRUSTDATA_API_KEY. Search follows cursor pagination;
responses are cached by request body. Set CRUSTDATA_CACHE_DIR to change cache.
"""
import hashlib, json, os, threading, time
from pathlib import Path
from typing import Any
import requests

BASE = os.getenv("CRUSTDATA_BASE_URL", "https://api.crustdata.com").rstrip("/")
CACHE_DIR = Path(os.getenv("CRUSTDATA_CACHE_DIR", ".cache")); CACHE_DIR.mkdir(parents=True, exist_ok=True)
SEARCH_FIELDS = ["crustdata_person_id", "basic_profile", "social_handles", "experience"]
ENRICH_FIELDS = ["basic_profile", "experience", "education", "skills", "social_handles"]

class CrustdataError(RuntimeError): pass
class _Throttle:
    def __init__(self, interval): self.interval, self.last, self.lock = interval, 0.0, threading.Lock()
    def wait(self):
        with self.lock:
            delay = self.interval - (time.monotonic() - self.last)
            if delay > 0: time.sleep(delay)
            self.last = time.monotonic()

_throttles = {"/person/search": _Throttle(2.1), "/person/enrich": _Throttle(4.2)}

def _headers():
    key = os.getenv("CRUSTDATA_API_KEY")
    if not key: raise CrustdataError("Set CRUSTDATA_API_KEY in your environment")
    return {"authorization": f"Bearer {key}", "x-api-version": os.getenv("CRUSTDATA_API_VERSION", "2025-11-01"), "content-type": "application/json"}

def _post(path: str, body: dict[str, Any], retries: int = 4):
    cache_key = hashlib.sha256((path + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if os.getenv("CRUSTDATA_DISABLE_CACHE") != "1" and cache_file.exists():
        try: return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): cache_file.unlink(missing_ok=True)
    last = None
    for attempt in range(retries + 1):
        _throttles[path].wait()
        try: response = requests.post(BASE + path, headers=_headers(), json=body, timeout=(10, 60))
        except requests.RequestException as exc:
            last = str(exc); time.sleep(min(2 ** attempt, 20)); continue
        if response.status_code == 200:
            try: data = response.json()
            except ValueError as exc: raise CrustdataError(f"{path} returned invalid JSON") from exc
            if os.getenv("CRUSTDATA_DISABLE_CACHE") != "1": cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
        if response.status_code == 429 or response.status_code >= 500:
            last = f"HTTP {response.status_code}: {response.text[:300]}"
            retry_after = response.headers.get("retry-after")
            try: delay = float(retry_after) if retry_after else min(2 ** (attempt + 1), 30)
            except ValueError: delay = min(2 ** (attempt + 1), 30)
            time.sleep(delay); continue
        raise CrustdataError(f"{path} HTTP {response.status_code}: {response.text[:500]}")
    raise CrustdataError(f"{path} failed after {retries + 1} attempts: {last}")

def _contains(field, value): return {"field": field, "type": "(.)", "value": value}

def _requested_location_parts(locations):
    """Extract requested city/country pairs from generated search variants."""
    pairs = []
    for location in locations or []:
        if not isinstance(location, str) or not location.strip():
            continue
        parts = [p.strip() for p in location.split(",") if p.strip()]
        if len(parts) >= 2:
            city, country = parts[0], parts[-1]
            aliases = {
                "bengaluru": ["Bengaluru", "Bangalore"],
                "bangalore": ["Bengaluru", "Bangalore"],
                "gurugram": ["Gurugram", "Gurgaon"],
                "gurgaon": ["Gurugram", "Gurgaon"],
            }
            cities = aliases.get(city.casefold(), [city])
            pairs.append({"city": cities, "country": country})
        elif len(parts) == 1:
            pairs.append({"city": [parts[0]], "country": None})
    # Stable de-duplication
    unique, seen = [], set()
    for pair in pairs:
        key = (tuple(x.casefold() for x in pair["city"]), (pair["country"] or "").casefold())
        if key not in seen:
            seen.add(key)
            unique.append(pair)
    return unique


def variant_to_filters(v):
    """Build title + geographic filters.

    City filtering is opt-in because available Crustdata field paths/operators
    can vary by API version/account. Set CRUSTDATA_CITY_FILTER=1 only after
    confirming basic_profile.location.city supports the configured operator.
    Country filtering remains the known-working broad discovery fallback.
    """
    conditions = []

    titles = list(dict.fromkeys(
        title.strip()
        for title in (v.titles or [])
        if isinstance(title, str) and title.strip()
    ))
    if titles:
        conditions.append({
            "op": "or",
            "conditions": [
                {
                    "field": "experience.employment_details.current.title",
                    "type": "(.)",
                    "value": title,
                }
                for title in titles
            ],
        })

    locations = _requested_location_parts(v.locations)
    countries = sorted({
        item["country"] for item in locations if item.get("country")
    })

    # Explicitly opt in only after validating this field/operator in Crustdata.
    if os.getenv("CRUSTDATA_CITY_FILTER", "0") == "1":
        city_values = list(dict.fromkeys(
            city
            for item in locations
            for city in item["city"]
        ))
        if city_values:
            conditions.append({
                "op": "or",
                "conditions": [
                    {
                        "field": os.getenv(
                            "CRUSTDATA_CITY_FIELD",
                            "basic_profile.location.city",
                        ),
                        "type": os.getenv("CRUSTDATA_CITY_OPERATOR", "="),
                        "value": city,
                    }
                    for city in city_values
                ],
            })

    if countries:
        country_conditions = [
            {
                "field": "basic_profile.location.country",
                "type": "=",
                "value": country,
            }
            for country in countries
        ]
        conditions.append(
            country_conditions[0]
            if len(country_conditions) == 1
            else {"op": "or", "conditions": country_conditions}
        )

    if not conditions:
        result = None
    else:
        result = conditions[0] if len(conditions) == 1 else {
            "op": "and",
            "conditions": conditions,
        }

    if os.getenv("CRUSTDATA_DEBUG", "0") == "1":
        print(
            "[DEBUG] Crustdata generated filters:",
            json.dumps(result, ensure_ascii=False, indent=2),
            flush=True,
        )
    return result


def search_people(filters: dict, limit: int = 25, fields=None, max_pages: int = 5) -> list[dict]:
    """Fetch up to limit*max_pages profiles, following next_cursor safely."""
    profiles, cursor, seen_cursors = [], None, set()
    for _ in range(max(1, max_pages)):
        body = {"filters": filters, "fields": fields or SEARCH_FIELDS, "limit": min(max(1, limit), 100)}
        if cursor: body["cursor"] = cursor
        payload = _post("/person/search", body)
        batch = payload.get("profiles") or []
        if not isinstance(batch, list): raise CrustdataError("Unexpected search response: 'profiles' is not a list")
        profiles.extend(batch)
        next_cursor = payload.get("next_cursor")
        if not next_cursor or next_cursor in seen_cursors or not batch: break
        seen_cursors.add(next_cursor); cursor = next_cursor
    return profiles

def profile_url(profile):
    return (profile.get("social_handles") or {}).get("professional_network_identifier", {}).get("profile_url")

def enrich_people(urls: list[str], fields=None) -> dict[str, dict | None]:
    out = {}
    clean_urls = list(dict.fromkeys(u for u in urls if isinstance(u, str) and u.strip()))
    for start in range(0, len(clean_urls), 25):
        chunk = clean_urls[start:start + 25]
        payload = _post("/person/enrich", {"professional_network_profile_urls": chunk, "fields": fields or ENRICH_FIELDS})
        if not isinstance(payload, list): raise CrustdataError("Unexpected enrich response: expected a list")
        for entry in payload:
            url = entry.get("matched_on")
            matches = entry.get("matches") or []
            best = max(matches, key=lambda m: float(m.get("confidence_score") or 0), default=None)
            out[url] = best.get("person_data") if best and float(best.get("confidence_score") or 0) >= 0.8 else None
        for url in chunk:
            out.setdefault(url, None)
    return out
