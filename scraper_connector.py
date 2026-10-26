"""
scraper_connector.py - Local Scraper Connector for Business Seeker.

Connects optionally to the `gosom/google-maps-scraper` Docker container
running locally (default: http://127.0.0.1:8080) to allow zero-API-cost
scraping of local business leads. Normalizes all responses to match the
Google Places API (New) schema and performs cascading deduplication.
"""

from __future__ import annotations

import csv
import io
import logging
import time
from typing import Any, Callable

import requests

from smart_filters import fuzzy_dedupe_places

logger = logging.getLogger(__name__)

DEFAULT_SCRAPER_URL = "http://127.0.0.1:8080"


def check_scraper_engine_status(base_url: str = DEFAULT_SCRAPER_URL) -> dict[str, Any]:
    """
    Check if the local google-maps-scraper engine is active and reachable.

    Tests GET /api/v1/jobs with a short 2-second timeout.

    Returns:
        dict: {"available": bool, "message": str}
    """
    clean_url = base_url.rstrip("/")
    endpoint = f"{clean_url}/api/v1/jobs"

    try:
        response = requests.get(endpoint, timeout=2)
        if response.status_code in (200, 201, 204):
            return {
                "available": True,
                "message": "Scraper engine is online and responding."
            }
        return {
            "available": False,
            "message": f"Scraper engine responded with HTTP {response.status_code}"
        }
    except requests.exceptions.Timeout:
        return {
            "available": False,
            "message": "Scraper engine request timed out (service busy or offline)."
        }
    except requests.exceptions.ConnectionError:
        return {
            "available": False,
            "message": "Scraper engine connection failed. Ensure Docker container is running."
        }
    except requests.exceptions.RequestException as err:
        return {
            "available": False,
            "message": f"Scraper engine check failed: {err}"
        }


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a rating value to float."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert review count to integer."""
    if val is None or val == "":
        return default
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace(".", "").strip()
        return int(val)
    except (ValueError, TypeError):
        return default


def normalize_scraper_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a raw result row from google-maps-scraper to the Google Places API schema.

    Schema:
        {
            "id": place_id or cid or "",
            "displayName": {"text": title},
            "formattedAddress": address,
            "nationalPhoneNumber": phone,
            "websiteUri": website,
            "rating": float,
            "userRatingCount": int,
            "googleMapsUri": maps_link,
            "businessStatus": "OPERATIONAL",
            "types": [category] or []
        }
    """
    if not isinstance(row, dict):
        row = {}

    place_id = row.get("place_id") or row.get("cid") or row.get("id") or ""
    
    title = row.get("title") or row.get("name") or ""
    if isinstance(title, dict):
        title = title.get("text", "")
        
    address = row.get("address") or row.get("formatted_address") or row.get("formattedAddress") or ""
    phone = row.get("phone") or row.get("national_phone_number") or row.get("nationalPhoneNumber") or ""
    website = row.get("web_site") or row.get("website") or row.get("websiteUri") or ""
    
    raw_rating = row.get("review_rating") if "review_rating" in row else row.get("rating")
    raw_reviews = row.get("review_count") if "review_count" in row else row.get("userRatingCount")
    
    rating = _safe_float(raw_rating, 0.0)
    user_rating_count = _safe_int(raw_reviews, 0)
    
    maps_uri = row.get("link") or row.get("googleMapsUri") or row.get("url") or ""
    
    category = row.get("category") or row.get("type") or row.get("categories") or ""
    if isinstance(category, list):
        types = [str(c).strip() for c in category if str(c).strip()]
    elif category and str(category).strip():
        types = [str(category).strip()]
    else:
        types = []

    return {
        "id": str(place_id).strip(),
        "displayName": {"text": str(title).strip()},
        "formattedAddress": str(address).strip(),
        "nationalPhoneNumber": str(phone).strip(),
        "websiteUri": str(website).strip(),
        "rating": rating,
        "userRatingCount": user_rating_count,
        "googleMapsUri": str(maps_uri).strip(),
        "businessStatus": "OPERATIONAL",
        "types": types,
    }


def get_dedupe_key(place: dict[str, Any]) -> str:
    """
    Determine the primary deduplication key based on cascading priority:
        1. place.get("id")
        2. place.get("googleMapsUri")
        3. f"{title.strip().lower()}|{address.strip().lower()}"
    """
    place_id = str(place.get("id") or "").strip()
    if place_id:
        return f"id:{place_id}"

    maps_uri = str(place.get("googleMapsUri") or place.get("link") or "").strip()
    if maps_uri:
        return f"uri:{maps_uri}"

    display_name = place.get("displayName")
    if isinstance(display_name, dict):
        title = display_name.get("text", "")
    elif isinstance(display_name, str):
        title = display_name
    else:
        title = place.get("title") or place.get("name") or ""

    address = place.get("formattedAddress") or place.get("address") or ""
    t_clean = str(title).strip().lower()
    a_clean = str(address).strip().lower()
    return f"{t_clean}|{a_clean}"


def dedupe_places(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Cascading deduplication of places preserving original encounter order.
    Uses fuzzy token and address similarity matching from smart_filters.

    Cascading priority keys:
        1. place.get("id")
        2. place.get("googleMapsUri")
        3. Fuzzy match on normalized name and normalized address

    Returns:
        list[dict]: Deduplicated places with ordering preserved.
    """
    deduped, _ = fuzzy_dedupe_places(places)
    return deduped


def run_scraper_job(
    query: str,
    lat: float | None = None,
    lon: float | None = None,
    max_results: int = 40,
    base_url: str = DEFAULT_SCRAPER_URL,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    poll_interval: float = 1.0,
    max_wait_seconds: int = 180,
) -> list[dict[str, Any]]:
    """
    Execute a full scrape job on the local google-maps-scraper engine:
        1. POST /api/v1/jobs - creates and starts search job
        2. GET /api/v1/jobs/{id} - polls until job completes or fails
        3. GET /api/v1/jobs/{id}/download - downloads CSV/JSON output
        4. Normalizes all rows into the Google Places API schema
        5. Performs cascading deduplication

    Args:
        query: Search query (e.g. "Oficinas Mecânicas em Moema, São Paulo").
        lat: Optional latitude coordinate anchor.
        lon: Optional longitude coordinate anchor.
        max_results: Maximum number of results to request.
        base_url: Scraper base URL (default: http://127.0.0.1:8080).
        progress_callback: Optional callable called on each poll with status dict.
        poll_interval: Delay in seconds between polling requests.
        max_wait_seconds: Maximum time to wait before timing out.

    Returns:
        list[dict]: List of normalized, deduplicated Google Places-compatible objects.

    Raises:
        RuntimeError: If job submission, polling, or download fails.
        TimeoutError: If the job exceeds max_wait_seconds.
    """
    clean_url = base_url.rstrip("/")

    # 1. Create Job
    create_url = f"{clean_url}/api/v1/jobs"
    payload: dict[str, Any] = {
        "keywords": [query],
        "depth": max_results,
        "lang": "pt-BR",
    }
    if lat is not None and lon is not None:
        payload["lat"] = str(lat)
        payload["lon"] = str(lon)

    try:
        create_resp = requests.post(create_url, json=payload, timeout=10)
    except requests.exceptions.RequestException as err:
        raise RuntimeError(f"Failed to connect to scraper at {create_url}: {err}") from err

    if create_resp.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Scraper rejected job creation: HTTP {create_resp.status_code} - {create_resp.text}"
        )

    try:
        job_data = create_resp.json()
    except Exception as json_err:
        raise RuntimeError(f"Invalid JSON received from job creation: {create_resp.text}") from json_err

    job_id = job_data.get("id") or job_data.get("job_id")
    if not job_id and isinstance(job_data.get("job"), dict):
        job_id = job_data["job"].get("id")

    if not job_id:
        raise RuntimeError(f"Scraper did not return a valid job ID: {job_data}")

    logger.info("Scraper job created with ID: %s", job_id)

    # 2. Poll Job Status
    job_url = f"{clean_url}/api/v1/jobs/{job_id}"
    start_time = time.time()

    while True:
        try:
            status_resp = requests.get(job_url, timeout=5)
        except requests.exceptions.RequestException as poll_err:
            logger.warning("Transient error polling job %s: %s", job_id, poll_err)
            time.sleep(poll_interval)
            continue

        if status_resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch job status: HTTP {status_resp.status_code}")

        try:
            job_info = status_resp.json()
        except Exception as json_err:
            raise RuntimeError(f"Failed to parse job status JSON: {status_resp.text}") from json_err

        status = str(job_info.get("status") or job_info.get("state") or "").strip().lower()

        if progress_callback and callable(progress_callback):
            try:
                progress_callback(job_info)
            except Exception as cb_err:
                logger.warning("Progress callback raised an exception: %s", cb_err)

        if status in {"completed", "finished", "done", "ok", "success"}:
            logger.info("Job %s completed successfully.", job_id)
            break

        if status in {"failed", "error", "cancelled"}:
            error_msg = job_info.get("error") or job_info.get("message") or status
            raise RuntimeError(f"Scraper job {job_id} terminated with failure: {error_msg}")

        if time.time() - start_time > max_wait_seconds:
            raise TimeoutError(f"Scraper job {job_id} timed out after {max_wait_seconds} seconds.")

        time.sleep(poll_interval)

    # 3. Download Results
    dl_url = f"{clean_url}/api/v1/jobs/{job_id}/download"
    try:
        dl_resp = requests.get(dl_url, timeout=30)
    except requests.exceptions.RequestException as dl_err:
        raise RuntimeError(f"Failed to download results for job {job_id}: {dl_err}") from dl_err

    if dl_resp.status_code != 200:
        raise RuntimeError(f"Download endpoint returned HTTP {dl_resp.status_code}: {dl_resp.text}")

    # 4. Parse Results (JSON or CSV)
    raw_rows: list[dict[str, Any]] = []
    content_type = dl_resp.headers.get("Content-Type", "")

    if "json" in content_type:
        try:
            parsed = dl_resp.json()
            if isinstance(parsed, list):
                raw_rows = parsed
            elif isinstance(parsed, dict):
                raw_rows = parsed.get("data") or parsed.get("results") or [parsed]
        except Exception:
            raw_rows = []

    if not raw_rows:
        # Fall back to CSV parsing
        try:
            text = dl_resp.text
            if text.strip():
                reader = csv.DictReader(io.StringIO(text))
                raw_rows = [dict(row) for row in reader]
        except Exception as csv_err:
            logger.error("Failed to parse CSV download for job %s: %s", job_id, csv_err)

    # 5. Normalize Schema
    normalized = [normalize_scraper_row(r) for r in raw_rows if isinstance(r, dict)]

    # 6. Cascading Deduplication
    deduped = dedupe_places(normalized)

    return deduped[:max_results]
