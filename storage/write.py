"""
storage/write.py
Writes a validated calendar dict to the Supabase app_config table (PATCH id=1).
Uses the service_role key so RLS is bypassed for the scraper write.
"""
import os
import requests
from datetime import datetime


def write_calendar(cal: dict, source_url: str = "") -> None:
    """PATCH the single app_config row with the new calendar dates."""
    supabase_url = os.environ["SUPABASE_URL"]
    service_key  = os.environ["SUPABASE_SERVICE_KEY"]

    payload = {
        "active_year":      cal["academic_year"].replace("/", "-"),
        "year_start":       cal.get("year_start") or cal.get("semester_1_start"),
        "year_end":         cal.get("year_end")   or cal.get("semester_2_end"),
        "semester_1_start": cal.get("semester_1_start"),
        "semester_1_end":   cal.get("semester_1_end"),
        "semester_2_start": cal.get("semester_2_start"),
        "semester_2_end":   cal.get("semester_2_end"),
        "source_name":      cal.get("source_name", "scraper"),
        "source_url":       source_url,
        "confirmed":        True,
        "updated_at":       datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Remove None values so we don't overwrite existing data with nulls
    payload = {k: v for k, v in payload.items() if v is not None}

    resp = requests.patch(
        f"{supabase_url}/rest/v1/app_config?id=eq.1",
        headers={
            "apikey":        service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type":  "application/json",
            "Prefer":        "return=minimal",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    print(f"✅ Wrote calendar for {cal['academic_year']} to Supabase app_config")


def calendar_already_confirmed(academic_year: str) -> bool:
    """
    Check if a confirmed calendar for academic_year already exists.
    Returns True if the DB already has dates → skip the scraper run.
    Uses anon key since this is a public SELECT.
    """
    supabase_url = os.environ["SUPABASE_URL"]
    anon_key     = os.environ["SUPABASE_ANON_KEY"]

    normalized = academic_year.replace("/", "-")
    resp = requests.get(
        f"{supabase_url}/rest/v1/app_config"
        f"?id=eq.1&select=active_year,semester_1_start,confirmed",
        headers={
            "apikey":        anon_key,
            "Authorization": f"Bearer {anon_key}",
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return False
    rows = resp.json()
    if not rows:
        return False
    row = rows[0]
    return (
        row.get("active_year") == normalized
        and row.get("confirmed") is True
        and row.get("semester_1_start") is not None
    )
