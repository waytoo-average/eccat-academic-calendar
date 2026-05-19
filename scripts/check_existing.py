"""
scripts/check_existing.py
Sets GitHub Actions output: needs_scrape=true/false
Run before the main scraper to skip LLM calls if calendar already confirmed.
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.write import calendar_already_confirmed


def current_academic_year() -> str:
    today = date.today()
    y = today.year
    return f"{y}/{y+1}" if today.month >= 9 else f"{y-1}/{y}"


if __name__ == "__main__":
    ay = current_academic_year()
    if calendar_already_confirmed(ay):
        print(f"Calendar for {ay} already confirmed.")
        # Set GitHub Actions output
        with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
            f.write("needs_scrape=false\n")
    else:
        print(f"No confirmed calendar for {ay}. Scraper will run.")
        with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
            f.write("needs_scrape=true\n")
