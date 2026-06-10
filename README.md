# AI Job Market Impact Tracker

A live dashboard tracking AI's impact on labour markets across six regions, grounded in the Anthropic Observed Exposure methodology (Massenkoff & McCrory, March 2026).

**Live site:** _(URL set after first Netlify deploy)_

## What this is

- A static HTML dashboard reading from JSON data files.
- A weekly refresh job that pulls fresh values and commits them to this repo.
- A downloadable historical CSV and weekly JSON snapshot archive.
- A user manual PDF explaining the methodology.

## Repo layout

```
.
├── index.html                       # main dashboard page
├── manual.pdf                       # user manual (rebuilt weekly)
├── netlify.toml                     # Netlify build/header/redirect config
├── assets/
│   ├── styles.css
│   └── dashboard.js
├── data/
│   ├── current.json                 # latest snapshot — drives the dashboard
│   ├── historical.csv               # master historical dataset (downloadable)
│   ├── snapshots_index.json         # list of available snapshots
│   └── snapshots/
│       └── YYYY-Wxx.json            # frozen weekly snapshots
├── scripts/
│   ├── seed_history.py              # one-time bootstrap
│   ├── update_data.py               # weekly refresh — run by GitHub Actions
│   └── build_manual.py              # rebuilds manual.pdf
└── .github/workflows/
    └── weekly-update.yml            # Monday 06:00 UTC cron
```

## Deployment — one-time setup

### 1. Create the GitHub repo

1. Sign in to https://github.com
2. Click **+** → **New repository**
3. Name it `ai-jobmarket-tracker` (or anything you prefer)
4. Make it **public** (required for the free Netlify and free GitHub Actions tiers)
5. **Don't** initialise it with a README, .gitignore, or licence — this repo already has those
6. Create the repo, then on the empty repo page copy the `git push` instructions

### 2. Push this folder to GitHub

From the `netlify-site` folder:

```bash
git init
git add .
git commit -m "Initial commit: AI Job Market Impact Tracker"
git branch -M main
git remote add origin https://github.com/<your-username>/ai-jobmarket-tracker.git
git push -u origin main
```

If you don't use the command line, you can drag-drop the files directly into the GitHub repo's web UI via the **Add file → Upload files** button.

### 3. Connect Netlify

1. Sign in to https://app.netlify.com
2. **Add new site** → **Import an existing project** → **GitHub**
3. Authorise Netlify to read your repos, pick `ai-jobmarket-tracker`
4. Build settings:
   - **Build command:** _leave empty_
   - **Publish directory:** _leave as the repo root (`.`)_
5. **Deploy site**

Netlify gives you a temporary URL like `https://random-words-12345.netlify.app`. You can change this under **Site settings → Change site name**, or connect a custom domain.

### 4. Confirm the weekly cron is active

GitHub Actions are enabled by default on public repos. To verify:

1. Open the repo's **Actions** tab
2. You should see the **Weekly data refresh** workflow listed
3. Click **Run workflow → Run workflow** to do a manual test run now
4. The workflow runs `scripts/update_data.py`, commits any data changes, and pushes — Netlify auto-redeploys on the push

The cron is set to `0 6 * * 1` (Mondays at 06:00 UTC). Adjust in `.github/workflows/weekly-update.yml` if you want a different time.

## Real data sources (v2, wired 2026-06-10)

Every KPI tile shows a **measured** or **modelled** badge.

**Measured pairs** (pulled live by `scripts/update_data.py` each Monday;
any fetch failure falls back to drift for that week, flagged modelled):

| KPI | Regions | Source |
|---|---|---|
| `exposed_posting_index` | US, UK (GB), EU (DE+FR mean - the EA folder has no sector file), AU | [Indeed Hiring Lab job_postings_tracker](https://github.com/hiring-lab/job_postings_tracker) - mean postings index across eight high-exposure sectors (Software Development; IT Operations & Helpdesk; Information Design & Documentation; Mathematics; Accounting; Banking & Finance; Administrative Assistance; Media & Communications) |
| `topq_unemp_delta` | US, UK, EU, AU | BLS CPS (20-24 vs 16+), ONS LMS (YBVQ 18-24 vs MGSX 16+), Eurostat `une_rt_m` (<25 vs total), ABS Labour Force (15-24 vs total). All seasonally adjusted |
| `ai_layoffs_ytd` | US | Challenger, Gray & Christmas monthly Job Cut Report - AI-cited cuts YTD, parsed from the latest report; manual override via `CHALLENGER_AI_YTD_THOUSANDS` env |

**Modelled (still synthetic):** everything else - including all KPIs for
India and APAC composite, and `ai_mention_postings` everywhere (Hiring Lab
cites AI-mention shares in blog posts but publishes no machine-readable
weekly series).

**Methodology notes**

- `topq_unemp_delta` was renamed to **"Early-career unemployment delta
  (proxy)"**: statistics agencies do not publish unemployment by AI
  exposure, so the measured series is youth minus overall unemployment
  rate. This is a deliberate, documented proxy change from the original
  top-quartile definition (Massenkoff & McCrory), whose cohort can only
  be computed from CPS microdata.
- Challenger history anchors (Mar/Apr/May 2026 month-ends) are derived
  from figures stated in the May 2026 report; the derivation chain is
  documented in `scripts/backfill_real_history.py`. Weeks before
  2026-03-31 stay modelled.
- 2026-06-10: snapshots W10-W23 were rewritten once by
  `backfill-history.yml` to replace synthetic values with real history
  for the wired pairs - a deliberate one-time break of the snapshot
  immutability rule, treated as a bug fix of the seeded data. Snapshots
  are immutable from W24 onward.

**Optional secret:** add `BLS_API_KEY` (free at
https://data.bls.gov/registrationEngine/) under **Settings → Secrets and
variables → Actions** to raise BLS rate limits. Works without it.

**One-time backfill:** Actions tab → "One-time history backfill (real
sources)" → Run workflow. Safe to re-run.

To wire more pairs: add an entry to `REAL_ADAPTERS` in
`scripts/update_data.py` - a function `(region, on_date_iso) -> (value,
source_name, source_url)`. Raise on failure; the caller handles drift
fallback and the measured/modelled flag.

## Editing the methodology

The user manual is rebuilt every weekly run by `scripts/build_manual.py`. To change the manual:

1. Edit `scripts/build_manual.py`
2. Run `python3 scripts/build_manual.py` locally to preview
3. Commit and push — the weekly cron will rebuild and redeploy

## Local preview

```bash
cd netlify-site
python3 -m http.server 8000
# then open http://localhost:8000
```

## Open data

- Master CSV: `/data/historical.csv` (also available at `/data.csv`)
- Latest snapshot: `/data/current.json`
- Snapshot archive: `/data/snapshots/YYYY-Wxx.json`
- Index of available snapshots: `/data/snapshots_index.json`

All snapshots are immutable. If a source revises a figure, the new value enters a future snapshot, never an old one.

## Methodology references

- Massenkoff & McCrory (2026), [Labor market impacts of AI](https://www.anthropic.com/research/labor-market-impacts)
- [Anthropic Economic Index](https://www.anthropic.com/economic-index)
- [Anthropic/EconomicIndex on Hugging Face](https://huggingface.co/datasets/Anthropic/EconomicIndex)
- Eloundou et al. (2023), GPTs are GPTs
- [WEF Future of Jobs Report 2025](https://www.weforum.org/publications/the-future-of-jobs-report-2025/)

Full reference list and methodology appendix are in `manual.pdf`.

## Licence

Code in this repository: MIT.
Data: derived from public reports cited per row in `historical.csv`. Attribute to "AI Job Market Impact Tracker" and link the source URL when republishing.
