"""
scripts/run_scraper.py
Main orchestrator: fetch → parse → validate → write.
Exits 0 on success or if calendar already confirmed.
Exits 1 on validation failure (triggers GitHub Actions failure → alert).
"""
import sys
import os
from datetime import date

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.fetch import fetch_all
from parser.extract import extract_calendar
from parser.validate import validate
from storage.write import write_calendar, calendar_already_confirmed


def current_academic_year() -> str:
    today = date.today()
    y = today.year
    return f"{y}/{y+1}" if today.month >= 9 else f"{y-1}/{y}"


def main():
    academic_year = current_academic_year()
    print(f"🔍 Checking for academic calendar: {academic_year}")

    # Skip if already confirmed in DB
    if calendar_already_confirmed(academic_year):
        print(f"✅ Calendar for {academic_year} already confirmed. Nothing to do.")
        sys.exit(0)

    # Fetch from all sources
    year = date.today().year if date.today().month >= 9 else date.today().year - 1
    sources = fetch_all(year)

    if not sources:
        print("⚠️  No text fetched from any source. Network issue?")
        sys.exit(1)

    # Try each source until we get a high/medium confidence result
    best_cal = None
    best_source_name = None

    for source_name, raw_text in sources.items():
        print(f"🤖 Parsing text from: {source_name}")
        try:
            cal = extract_calendar(raw_text, source_name=source_name)
        except Exception as e:
            print(f"  ❌ LLM extraction failed for {source_name}: {e}")
            continue

        print(f"  confidence={cal.get('confidence')}  academic_year={cal.get('academic_year')}")

        result = validate(cal)

        if result.warnings:
            for w in result.warnings:
                print(f"  ⚠️  {w}")

        if result.passed:
            best_cal = cal
            best_source_name = source_name
            print(f"  ✅ Validation passed for {source_name}")
            break
        else:
            for e in result.errors:
                print(f"  ❌ {e}")

    if best_cal is None:
        print("❌ No source produced a valid calendar. Human review required.")
        sys.exit(1)

    # Write to Supabase
    source_url = f"https://english.ahram.org.eg" if best_source_name == "ahram" else "https://scu.eg/en/news/"
    write_calendar(best_cal, source_url=source_url)
    print(f"🎉 Done — {academic_year} calendar written to Supabase.")
    sys.exit(0)


if __name__ == "__main__":
    main()
