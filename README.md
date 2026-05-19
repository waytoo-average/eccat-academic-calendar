# ECCAT Academic Calendar Scraper

Fully automated, zero-cost system that:
1. **Scrapes** the Egyptian SCU academic calendar announcement every year
2. **Writes** semester start/end dates to the Supabase `app_config` table
3. **Auto-switches** `active_semester` daily based on today's date vs the stored dates
4. **Alerts** you if something goes wrong (ntfy push notification)

No human action needed under normal operation — not this year, not next year.

---

## Automation overview

```
Every year (June–July)                    Every day (00:05 UTC)
──────────────────────                    ─────────────────────
GitHub Actions cron                       Supabase pg_cron
  │                                         │
  │  Scrape SCU announcement                │  SELECT refresh_active_semester()
  │  (DuckDuckGo → Youm7 → Masrawy          │
  │   → MHE → SCU direct)                  │  Updates active_semester in
  │                                         │  app_config based on today
  │  Groq LLM extracts dates               │  vs semester_2_start date
  │                                         │
  │  Validator checks dates                ▼
  │                                       app_config.active_semester
  │  POST to update-calendar              auto-switches on the correct day
  │  Edge Function
  │
  ▼
app_config updated with new year's dates
```

**`active_semester` is fully automatic** — it switches from "Semester 1" to
"Semester 2" on `semester_2_start` day with no manual action. The same happens
in reverse for the next academic year once the scraper writes new dates.

---

## Security model

```
GitHub Actions scraper
        │
        │  POST /functions/v1/update-calendar
        │  Authorization: Bearer <anon_key>   (satisfies Supabase JWT check)
        │  X-Calendar-Secret: <secret>        (our write guard)
        ▼
Supabase Edge Function  (update-calendar)
        │  validates X-Calendar-Secret from Deno.env
        │  uses service_role key internally — never exposed outside Supabase
        ▼
app_config table
```

The scraper never holds the service_role key.

---

## One-time setup

### 1. Create a new public GitHub repository
Public repos get unlimited free GitHub Actions minutes.

### 2. Set the Edge Function secret in Supabase

**Supabase Dashboard → Edge Functions → update-calendar → Secrets:**

| Key | Value |
|-----|-------|
| `CALENDAR_WRITE_SECRET` | A strong random string (`openssl rand -hex 32`) |

### 3. Add GitHub Actions secrets

**Repo Settings → Secrets and variables → Actions:**

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | `https://vqxvkpbbwssywdntitjf.supabase.co` |
| `SUPABASE_ANON_KEY` | Anon/public key from Supabase Dashboard |
| `CALENDAR_WRITE_SECRET` | Same value as the Edge Function secret above |
| `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) — free account |
| `NTFY_TOPIC` | Any unique string — subscribe in ntfy app for alerts |

> `SUPABASE_SERVICE_ROLE_KEY` is **never** used by the scraper.

### 4. Enable workflow write permissions

**Repo Settings → Actions → General → Workflow permissions → Read and write permissions**

### 5. Push and test

```bash
git init && git add . && git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ORG/eccat-academic-calendar.git
git push -u origin main
```

Trigger manually: **Actions → Scrape academic calendar → Run workflow**

---

## Cron schedule

| Job | When | Purpose |
|-----|------|---------|
| GitHub Actions `scrape.yml` | Weekly May–Aug, daily June–July | Fetch + write new year's dates |
| GitHub Actions `health_check.yml` | Every Monday + July 1st | Alert if dates are stale |
| Supabase pg_cron | Daily at 00:05 UTC | Auto-switch `active_semester` |

---

## Receiving alerts

Install **ntfy** on your phone, subscribe to your `NTFY_TOPIC` string.
You'll be alerted if the health check finds no confirmed calendar by July.

- Android: [ntfy on Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- iOS: [ntfy on App Store](https://apps.apple.com/app/ntfy/id1625396347)

---

## Yearly maintenance (expected: zero)

Under normal operation you receive one ntfy notification per year confirming
the new calendar was saved. Nothing else is needed.

If no notification arrives by **July 15**:
1. Check **Actions** tab for failed runs
2. Manually update `app_config` via Supabase Dashboard SQL editor:

```sql
UPDATE app_config SET
  active_year      = '2026-2027',
  year_start       = '2026-09-19',
  year_end         = '2027-05-20',
  semester_1_start = '2026-09-19',
  semester_1_end   = '2027-01-07',
  semester_2_start = '2027-02-06',
  semester_2_end   = '2027-05-20',
  source_name      = 'admin',
  confirmed        = true,
  updated_at       = now()
WHERE id = 1;
-- active_semester will be auto-derived by the trigger
```

---

## Repository structure

```
eccat-academic-calendar/
├── .github/workflows/
│   ├── scrape.yml          — Scraper cron (May–Aug)
│   └── health_check.yml    — Weekly + July 1st health check
├── scraper/
│   └── fetch.py            — Multi-source fetcher (DDG → Youm7 → Masrawy → MHE → SCU)
├── parser/
│   ├── extract.py          — Groq LLM date extraction (llama-3.1-8b-instant)
│   └── validate.py         — Deterministic sanity checks
├── storage/
│   └── write.py            — POST to Supabase Edge Function
├── scripts/
│   ├── run_scraper.py      — Main orchestrator
│   ├── check_existing.py   — Skip guard
│   └── health_check.py     — Stale-data detector + ntfy alert
├── requirements.txt
└── README.md
```

---

## app_config columns written by scraper

| Column | Example | Auto-managed? |
|--------|---------|---------------|
| `active_year` | `2025-2026` | By scraper |
| `year_start` | `2025-09-20` | By scraper |
| `year_end` | `2026-05-21` | By scraper |
| `semester_1_start` | `2025-09-20` | By scraper |
| `semester_1_end` | `2026-01-01` | By scraper |
| `semester_2_start` | `2026-02-07` | By scraper |
| `semester_2_end` | `2026-05-21` | By scraper |
| `active_semester` | `Semester 1` or `Semester 2` | **By pg_cron daily** |
| `source_name` | `duckduckgo` / `youm7` / `admin` | By scraper |
| `confirmed` | `true` | By scraper |
