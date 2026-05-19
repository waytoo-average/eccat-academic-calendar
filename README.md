# ECCAT Academic Calendar Scraper

Automatically scrapes the Egyptian Supreme Council of Universities (SCU) annual
academic calendar announcement and writes it to the ECCAT Supabase `app_config` table.

**Stack:** Python + Groq (free LLM) + GitHub Actions (free cron) + Supabase Edge Function  
**Cost:** $0

---

## Security model

```
GitHub Actions scraper
        │
        │  POST /functions/v1/update-calendar
        │  Authorization: Bearer <CALENDAR_WRITE_SECRET>
        ▼
Supabase Edge Function  (update-calendar)
        │  validates secret from Deno.env
        │  uses service_role key internally — never exposed outside Supabase
        ▼
app_config table
```

The scraper **never holds the service_role key**. It only holds:
- `SUPABASE_ANON_KEY` — public read-only key, safe to expose
- `CALENDAR_WRITE_SECRET` — a custom shared secret you generate; useless without the Edge Function

---

## How it works

1. GitHub Actions runs weekly from May, daily in June–July
2. Checks if a confirmed calendar already exists for this academic year (skip if yes)
3. Fetches raw text from SCU news page and Al-Ahram English
4. Groq LLM (`llama-3.1-8b-instant`) extracts structured dates
5. Validator applies deterministic sanity checks (semester months, lengths, chronology)
6. On pass: POSTs to `update-calendar` Edge Function → DB write happens server-side
7. All 4 ECCAT apps pick up the new dates on next launch via `AppConfigService`

---

## One-time setup

### 1. Create a new public GitHub repository
Public repos get unlimited free GitHub Actions minutes.

### 2. Set the Edge Function secret in Supabase

Go to **Supabase Dashboard → Edge Functions → update-calendar → Secrets** and add:

| Key | Value |
|-----|-------|
| `CALENDAR_WRITE_SECRET` | A strong random string (generate with `openssl rand -hex 32`) |

The `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are automatically available
inside every Edge Function — you do not need to set them manually.

### 3. Add GitHub Actions secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | `https://vqxvkpbbwssywdntitjf.supabase.co` |
| `SUPABASE_ANON_KEY` | The anon/public key from Supabase Dashboard (safe — read-only) |
| `CALENDAR_WRITE_SECRET` | The **same** value you set in the Edge Function secret above |
| `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) — free account |
| `NTFY_TOPIC` | A unique topic string e.g. `eccat-calendar-alerts-xyz` — for push alerts via [ntfy.sh](https://ntfy.sh) (free, no account needed) |

> The `SUPABASE_SERVICE_ROLE_KEY` is **not** a GitHub secret and is **never** used by the scraper.

### 4. Push this repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ORG/eccat-academic-calendar.git
git push -u origin main
```

### 5. Test manually

Trigger the scraper once from **Actions → Scrape academic calendar → Run workflow**
to verify the end-to-end flow before the scheduled runs begin.

---

## Receiving alerts

Install the **ntfy** app on your phone:
- Android: [ntfy on Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
- iOS: [ntfy on App Store](https://apps.apple.com/app/ntfy/id1625396347)

Subscribe to your topic name (same as `NTFY_TOPIC` secret).
You'll get a push notification if the health check finds a problem.

---

## Yearly maintenance (normal operation)

Under normal operation you should receive a notification in June/July confirming
the new calendar was saved. That's the only interaction expected.

If no notification arrives by **July 15**:
1. Check the Actions tab for failed runs
2. If scraper failed: manually update the `app_config` row in Supabase Dashboard:

```sql
UPDATE app_config SET
  active_year      = '2025-2026',
  year_start       = '2025-09-20',
  year_end         = '2026-06-30',
  semester_1_start = '2025-09-20',
  semester_1_end   = '2026-01-08',
  semester_2_start = '2026-02-07',
  semester_2_end   = '2026-06-30',
  source_name      = 'admin',
  confirmed        = true,
  updated_at       = now()
WHERE id = 1;
```

---

## Repository structure

```
eccat-academic-calendar/
├── .github/workflows/
│   ├── scrape.yml          — Main scraper cron (May–Aug)
│   └── health_check.yml    — Weekly + July 1st health check
├── scraper/
│   └── fetch.py            — HTTP fetch from SCU + Al-Ahram
├── parser/
│   ├── extract.py          — Groq LLM date extraction
│   └── validate.py         — Deterministic sanity checks
├── storage/
│   └── write.py            — POST to Supabase Edge Function (no service key)
├── scripts/
│   ├── run_scraper.py      — Main orchestrator
│   ├── check_existing.py   — Skip guard (sets needs_scrape output)
│   └── health_check.py     — Stale-data detector + ntfy alert
├── requirements.txt
└── README.md
```

---

## app_config columns written

| Column | Example |
|--------|---------|
| `active_year` | `2025-2026` |
| `year_start` | `2025-09-20` |
| `year_end` | `2026-06-30` |
| `semester_1_start` | `2025-09-20` |
| `semester_1_end` | `2026-01-08` |
| `semester_2_start` | `2026-02-07` |
| `semester_2_end` | `2026-06-30` |
| `source_name` | `scu` / `ahram` / `admin` |
| `confirmed` | `true` |

The `active_semester` field is **not written by the scraper** — it is managed
manually since semester switching is a deliberate operational decision.
