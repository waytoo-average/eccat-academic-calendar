"""
storage/write.py
Writes a validated calendar dict to Supabase via the `update-calendar` Edge Function.

Security model:
  - The scraper only holds CALENDAR_WRITE_SECRET (a custom shared secret).
  - The service_role key NEVER leaves Supabase infrastructure.
  - The Edge Function validates the secret and performs the DB write server-side.
"""
import os
import requests
from datetime import date


_SUPABASE_URL   = None   # resolved lazily from env
_WRITE_SECRET   = None   # resolved lazily from env


def _edge_url() -> str:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise EnvironmentError("SUPABASE_URL env var is not set")
    return f"{url}/functions/v1/update-calendar"


def _secret() -> str:
    secret = os.environ.get("CALENDAR_WRITE_SECRET", "")
    if not secret:
        raise EnvironmentError("CALENDAR_WRITE_SECRET env var is not set")
    return secret


def write_calendar(cal: dict, source_url: str = "") -> None:
    """
    POST the validated calendar dict to the Supabase Edge Function.
    The Edge Function holds the service_role key — we never touch it here.
    """
    payload = {
        "active_year":      cal.get("academic_year", "").replace("/", "-"),
        "year_start":       cal.get("year_start") or cal.get("semester_1_start"),
        "year_end":         cal.get("year_end")   or cal.get("semester_2_end"),
        "semester_1_start": cal.get("semester_1_start"),
        "semester_1_end":   cal.get("semester_1_end"),
        "semester_2_start": cal.get("semester_2_start"),
        "semester_2_end":   cal.get("semester_2_end"),
        "source_name":      cal.get("source_name", "scraper"),
        "source_url":       source_url or None,
    }

    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    resp = requests.post(
        _edge_url(),
        headers={
            "Authorization": f"Bearer {_secret()}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=20,
    )

    if resp.status_code == 401:
        raise PermissionError("Edge Function rejected the write secret. Check CALENDAR_WRITE_SECRET.")
    if resp.status_code == 422:
        raise ValueError(f"Edge Function validation failed: {resp.text}")

    resp.raise_for_status()
    print(f"✅ Wrote calendar for {payload.get('active_year')} via Edge Function")


def calendar_already_confirmed(academic_year: str) -> bool:
    """
    Check if a confirmed calendar for academic_year already exists.
    Uses the public anon key — this is a safe read-only check.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon_key     = os.environ.get("SUPABASE_ANON_KEY", "")

    if not supabase_url or not anon_key:
        return False

    normalized = academic_year.replace("/", "-")
    try:
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
    except Exception:
        return False
