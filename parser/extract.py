"""
parser/extract.py
Uses Groq (free tier) to extract structured academic calendar dates from raw text.
Model: llama-3.1-8b-instant  — fast, free, sufficient for structured extraction.
"""
import json
import os
from groq import Groq

SCHEMA = {
    "academic_year":   "e.g. 2025/2026",
    "year_start":      "YYYY-MM-DD — first day of the academic year (= semester_1_start)",
    "year_end":        "YYYY-MM-DD — last day of the academic year (= semester_2_end)",
    "semester_1_start": "YYYY-MM-DD",
    "semester_1_end":   "YYYY-MM-DD",
    "semester_2_start": "YYYY-MM-DD",
    "semester_2_end":   "YYYY-MM-DD",
    "source_name":     "scu | ahram | other",
    "confidence":      "high | medium | low",
    "notes":           "any caveats or ambiguities",
}

SYSTEM_PROMPT = f"""You are a structured data extractor specializing in Egyptian university academic calendars.
Extract dates from the provided text and return ONLY a valid JSON object matching this schema — no preamble, no markdown fences, no extra keys:

{json.dumps(SCHEMA, indent=2)}

Rules:
- All dates must be ISO 8601 (YYYY-MM-DD). If only month+year is known, use the 1st of that month.
- year_start equals semester_1_start. year_end equals semester_2_end.
- Semester 1 typically starts in September or October.
- Semester 2 typically starts in February or March.
- If a field cannot be determined, set it to null.
- confidence = "high" if all 4 semester dates are explicitly stated, "medium" if some are inferred, "low" if the text contains no calendar.
- If the text has no academic calendar announcement, return all date fields as null and confidence as "low"."""


def extract_calendar(raw_text: str, source_name: str = "unknown") -> dict:
    """Call Groq LLM to extract calendar dates from raw_text. Returns parsed dict."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": raw_text[:10000]},  # token guard
        ],
        max_tokens=512,
        temperature=0,
    )

    text = response.choices[0].message.content.strip()

    # Strip accidental markdown fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]

    result = json.loads(text)
    result.setdefault("source_name", source_name)
    return result
