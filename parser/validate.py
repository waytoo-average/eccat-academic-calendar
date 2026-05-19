"""
parser/validate.py
Deterministic sanity checks on the extracted calendar dict.
"""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ValidationResult:
    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def validate(cal: dict) -> ValidationResult:
    warnings, errors = [], []

    # Confidence gate — if LLM says low, nothing to validate
    if cal.get("confidence") == "low":
        errors.append("LLM confidence is low — likely no calendar found in scraped text.")
        return ValidationResult(passed=False, errors=errors)

    # All four critical dates must be present
    critical = ["semester_1_start", "semester_1_end", "semester_2_start", "semester_2_end"]
    for f in critical:
        if not cal.get(f):
            errors.append(f"Missing critical field: {f}")

    if errors:
        return ValidationResult(passed=False, errors=errors)

    try:
        s1_start = date.fromisoformat(cal["semester_1_start"])
        s1_end   = date.fromisoformat(cal["semester_1_end"])
        s2_start = date.fromisoformat(cal["semester_2_start"])
        s2_end   = date.fromisoformat(cal["semester_2_end"])
    except ValueError as e:
        errors.append(f"Date parse error: {e}")
        return ValidationResult(passed=False, errors=errors)

    # Semester 1 must start in September or October
    if s1_start.month not in (9, 10):
        errors.append(f"Semester 1 start month {s1_start.month} unexpected (expected 9 or 10)")

    # Semester 2 must start in February or March
    if s2_start.month not in (2, 3):
        errors.append(f"Semester 2 start month {s2_start.month} unexpected (expected 2 or 3)")

    # Chronological order
    if s1_end >= s2_start:
        errors.append("Semester 1 end is not before Semester 2 start")

    if s1_start >= s1_end:
        errors.append("Semester 1 start is not before Semester 1 end")

    if s2_start >= s2_end:
        errors.append("Semester 2 start is not before Semester 2 end")

    # Semester lengths should be roughly 12–20 weeks
    s1_weeks = (s1_end - s1_start).days / 7
    s2_weeks = (s2_end - s2_start).days / 7
    if not (10 <= s1_weeks <= 22):
        warnings.append(f"Semester 1 length {s1_weeks:.1f} weeks is unusual")
    if not (10 <= s2_weeks <= 22):
        warnings.append(f"Semester 2 length {s2_weeks:.1f} weeks is unusual")

    # Academic year sanity
    current_year = date.today().year
    expected_years = {f"{current_year}/{current_year+1}", f"{current_year-1}/{current_year}"}
    if cal.get("academic_year") and cal["academic_year"] not in expected_years:
        warnings.append(
            f"Academic year '{cal['academic_year']}' doesn't match expected {expected_years}"
        )

    return ValidationResult(passed=len(errors) == 0, warnings=warnings, errors=errors)
