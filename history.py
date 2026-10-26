"""
history.py - Local Seen-Leads History Manager for Business Seeker.

Provides persistent storage of previously found and qualified leads in a
lightweight JSON file (`leads_vistos.json`) in the project root. This avoids
re-prospecting already contacted or previously analyzed local businesses.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default location for the history file in the project root
DEFAULT_HISTORY_FILE = str(Path(__file__).resolve().parent / "leads_vistos.json")


def _resolve_path(filepath: str | None = None) -> str:
    """Return the absolute path to the history file."""
    if filepath:
        return os.path.abspath(filepath)
    return DEFAULT_HISTORY_FILE


def load_history(filepath: str | None = None) -> dict[str, dict]:
    """
    Load the seen-leads history dictionary from disk.

    Handles missing files, empty files, or corrupted JSON gracefully
    without raising exceptions or crashing the application.

    Returns:
        dict[str, dict]: Mapping of lead_id -> lead_metadata.
    """
    path = _resolve_path(filepath)

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            data = json.loads(content)
            if isinstance(data, dict):
                return data
            logger.warning("History file at %s does not contain a JSON object. Resetting to empty.", path)
            return {}
    except (json.JSONDecodeError, OSError, ValueError) as err:
        logger.warning("Failed to load history from %s (%s). Starting with empty history.", path, err)
        return {}


def save_history(history: dict[str, dict], filepath: str | None = None) -> bool:
    """
    Save the history dictionary atomically to disk.

    Args:
        history: Dictionary mapping lead_id to lead info dict.
        filepath: Optional custom path to save to.

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    path = _resolve_path(filepath)
    parent_dir = os.path.dirname(path)

    try:
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Atomic write via temporary file in the same directory
        temp_fd, temp_path = tempfile.mkstemp(dir=parent_dir, prefix="leads_vistos_", suffix=".tmp")
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, path)
            return True
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
    except Exception as err:
        logger.error("Failed to save history to %s: %s", path, err)
        # Direct fallback write attempt
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as fallback_err:
            logger.error("Fallback save also failed for %s: %s", path, fallback_err)
            return False


def extract_lead_identifier(lead: dict[str, Any] | str) -> str:
    """
    Extract a unique string identifier from a lead dictionary or string.

    Priority:
        1. lead['id'] or lead['place_id'] or lead['cid']
        2. lead['googleMapsUri'] or lead['Google Maps'] or lead['link']
        3. f"{business_name.strip().lower()}|{address.strip().lower()}"
    """
    if isinstance(lead, str):
        return lead.strip()

    if not isinstance(lead, dict):
        return ""

    # Priority 1: Direct ID fields
    lead_id = lead.get("id") or lead.get("place_id") or lead.get("cid")
    if lead_id and str(lead_id).strip():
        return str(lead_id).strip()

    # Priority 2: Maps URI
    maps_uri = lead.get("googleMapsUri") or lead.get("Google Maps") or lead.get("link")
    if maps_uri and str(maps_uri).strip():
        return str(maps_uri).strip()

    # Priority 3: Fallback on normalized name + address
    display_name = lead.get("displayName")
    if isinstance(display_name, dict):
        name = display_name.get("text", "")
    elif isinstance(display_name, str):
        name = display_name
    else:
        name = lead.get("Nome da Empresa") or lead.get("title") or lead.get("name") or ""

    address = lead.get("formattedAddress") or lead.get("Endereço") or lead.get("address") or ""

    name_clean = str(name).strip().lower()
    addr_clean = str(address).strip().lower()

    if name_clean or addr_clean:
        return f"{name_clean}|{addr_clean}"

    return ""


def mark_leads_as_seen(
    leads: list[dict[str, Any]],
    filepath: str | None = None,
    history: dict[str, dict] | None = None
) -> int:
    """
    Record leads into the local seen-leads history.

    Stores:
        - identifier (place_id / id / maps_uri)
        - business name
        - formatted address
        - google maps uri
        - timestamp in ISO format (UTC)

    Args:
        leads: List of lead dictionaries (Places API schema or app.py format).
        filepath: Optional custom path to leads_vistos.json.
        history: Optional pre-loaded history dict. If None, loaded from disk.

    Returns:
        int: Count of newly marked leads.
    """
    if history is None:
        history = load_history(filepath)

    newly_marked = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for lead in leads:
        if not isinstance(lead, dict):
            continue

        lead_id = extract_lead_identifier(lead)
        if not lead_id:
            continue

        # Extract readable fields
        display_name = lead.get("displayName")
        if isinstance(display_name, dict):
            name = display_name.get("text", "")
        elif isinstance(display_name, str):
            name = display_name
        else:
            name = lead.get("Nome da Empresa") or lead.get("title") or lead.get("name") or ""

        address = lead.get("formattedAddress") or lead.get("Endereço") or lead.get("address") or ""
        maps_uri = lead.get("googleMapsUri") or lead.get("Google Maps") or lead.get("link") or ""

        # Check if already present
        if not is_lead_seen(lead, history=history, filepath=filepath):
            newly_marked += 1

        history[lead_id] = {
            "id": lead_id,
            "name": str(name).strip(),
            "address": str(address).strip(),
            "maps_uri": str(maps_uri).strip(),
            "seen_at": now_iso,
        }

    save_history(history, filepath)
    return newly_marked


def is_lead_seen(
    lead_id: str | dict[str, Any],
    history: dict[str, dict] | None = None,
    filepath: str | None = None
) -> bool:
    """
    Check if a specific lead has already been recorded in history.

    Supports querying by:
        - Exact string ID (place_id, maps_uri, or 'name|address')
        - Full lead dict

    Args:
        lead_id: String ID or lead dict.
        history: Optional pre-loaded history dict. If None, loaded from disk.
        filepath: Optional custom path to leads_vistos.json.

    Returns:
        bool: True if the lead exists in history, False otherwise.
    """
    if history is None:
        history = load_history(filepath)

    if not history:
        return False

    if isinstance(lead_id, dict):
        extracted = extract_lead_identifier(lead_id)
        if extracted and extracted in history:
            return True

        # Check cross-field references if extracted key didn't match directly
        place_id = str(lead_id.get("id") or lead_id.get("place_id") or lead_id.get("cid") or "").strip()
        maps_uri = str(lead_id.get("googleMapsUri") or lead_id.get("Google Maps") or lead_id.get("link") or "").strip()

        if place_id and place_id in history:
            return True
        if maps_uri and maps_uri in history:
            return True

        # Search inside stored entries
        for entry in history.values():
            if not isinstance(entry, dict):
                continue
            if place_id and (entry.get("id") == place_id or entry.get("place_id") == place_id):
                return True
            if maps_uri and (entry.get("maps_uri") == maps_uri or entry.get("googleMapsUri") == maps_uri):
                return True
            if extracted and entry.get("id") == extracted:
                return True
        return False

    # String query
    target = str(lead_id).strip()
    if not target:
        return False

    if target in history:
        return True

    # Search in entry properties (e.g. if target is maps_uri but key was place_id)
    for entry in history.values():
        if not isinstance(entry, dict):
            continue
        if entry.get("id") == target or entry.get("maps_uri") == target or entry.get("place_id") == target:
            return True

    return False


def filter_unseen_leads(
    leads: list[dict[str, Any]],
    history: dict[str, dict] | None = None,
    filepath: str | None = None
) -> tuple[list[dict[str, Any]], int]:
    """
    Filter out leads that have already been recorded as seen.

    Args:
        leads: List of lead dictionaries.
        history: Optional pre-loaded history dict. If None, loaded from disk.
        filepath: Optional custom path to leads_vistos.json.

    Returns:
        tuple[list[dict], int]:
            - list of unseen leads
            - count of filtered out (previously seen) leads
    """
    if history is None:
        history = load_history(filepath)

    unseen: list[dict[str, Any]] = []
    filtered_count = 0

    for lead in leads:
        if is_lead_seen(lead, history=history, filepath=filepath):
            filtered_count += 1
        else:
            unseen.append(lead)

    return unseen, filtered_count


def clear_history(filepath: str | None = None) -> bool:
    """
    Clear the local history file.

    Removes the file from disk or truncates it to an empty JSON object.

    Args:
        filepath: Optional custom path to leads_vistos.json.

    Returns:
        bool: True if cleared successfully, False otherwise.
    """
    path = _resolve_path(filepath)
    try:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                return save_history({}, filepath=path)
        return True
    except Exception as err:
        logger.error("Failed to clear history at %s: %s", path, err)
        try:
            return save_history({}, filepath=path)
        except Exception:
            return False
