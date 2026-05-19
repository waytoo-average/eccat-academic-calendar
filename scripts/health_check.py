"""
scripts/health_check.py
Runs every Monday + July 1st via GitHub Actions.
Alerts if no confirmed calendar exists for the upcoming academic year by July.
"""
import os
import sys
import requests
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUPABASE_URL = os.environ["SUPABASE_URL"]
ANON_KEY     = os.environ["SUPABASE_ANON_KEY"]
NTFY_TOPIC   = os.environ.get("NTFY_TOPIC")  # e.g. "eccat-calendar-alerts"


def alert(msg: str):
    print(f"⚠️  ALERT: {msg}")
    if NTFY_TOPIC:
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=msg.encode("utf-8"),
                headers={"Title": "ECCAT Academic Calendar Alert", "Priority": "high"},
                timeout=10,
            )
        except Exception as e:
            print(f"  ntfy.sh send failed: {e}")


def supabase_get(select: str) -> list[dict]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/app_config?id=eq.1&select={select}",
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def current_academic_year() -> str:
    today = date.today()
    y = today.year
    return f"{y}-{y+1}" if today.month >= 9 else f"{y-1}-{y}"


def main():
    today = date.today()
    upcoming_ay = current_academic_year()

    print(f"🏥 Health check — {today}  upcoming: {upcoming_ay}")

    rows = supabase_get("active_year,semester_1_start,semester_2_start,confirmed,updated_at")
    if not rows:
        alert("app_config table returned no rows. Database issue?")
        sys.exit(1)

    row = rows[0]
    confirmed = row.get("confirmed") is True
    has_dates = row.get("semester_1_start") and row.get("semester_2_start")
    stored_year = row.get("active_year", "")

    # Check 1: upcoming year has confirmed dates (only warn from July onward)
    if today.month >= 7 and (stored_year != upcoming_ay or not confirmed or not has_dates):
        alert(
            f"No confirmed calendar for {upcoming_ay} found in Supabase app_config.\n"
            f"Currently stored: active_year={stored_year}, confirmed={confirmed}, has_dates={has_dates}.\n"
            f"Academic year starts in September — manual entry may be required.\n"
            f"Repo: https://github.com/YOUR_ORG/eccat-academic-calendar"
        )

    # Check 2: data is stale (updated_at older than 400 days means last year's data)
    updated_at_str = row.get("updated_at", "")
    if updated_at_str:
        try:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            age_days = (datetime.now(updated_at.tzinfo) - updated_at).days
            if age_days > 400:
                alert(
                    f"app_config.updated_at is {age_days} days old ({updated_at_str}).\n"
                    f"The calendar data may be from last year. Scraper may not have run."
                )
        except Exception:
            pass

    print("✅ Health check complete.")


if __name__ == "__main__":
    main()
