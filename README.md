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

## Simple / Deep view and derived metrics (added 2026-08-14)

The dashboard has two reading levels, toggled at the top of the Live
dashboard section (persisted per browser):

- **Simple** (default): one **AI Pressure Index** (0-100) per region plus
  four plain-language pillar signals - *Job displacement*, *Hiring
  pullback*, *Early-career squeeze*, *AI adoption pace* - each with a
  status word, month-over-month delta, sparkline, and a "% measured"
  confidence chip.
- **Deep**: everything under the hood - all ten raw KPI tiles with
  measured/modelled badges, the full analytical charts, and an "Under the
  hood" lineage panel on every pillar card showing each input's raw value
  → calibration band → normalized score → weight → contribution, with its
  source link and provenance badge.

Derived metrics are computed **client-side** in `assets/dashboard.js` from
`data/current.json` + `data/historical.csv` - the lineage shown *is* the
calculation, so dashboard and documentation cannot drift apart. Formulas,
calibration bands and weights are specified in
[`DERIVED_METRICS.md`](DERIVED_METRICS.md). Scores compare a region to
itself over time; they are not cross-country exposure rankings (consistent
with the locked Observed Exposure methodology).

## Real data sources (v3, wired 2026-08-14; v2 2026-06-10)

Every KPI tile shows a **measured** or **modelled** badge.

**Measured pairs** (pulled live by `scripts/update_data.py` each Monday;
any fetch failure carries the previous value forward, flagged modelled):

| KPI | Regions | Source |
|---|---|---|
| `exposed_posting_index` | US, UK (GB), EU (DE+FR mean - the EA folder has no sector file), AU | [Indeed Hiring Lab job_postings_tracker](https://github.com/hiring-lab/job_postings_tracker) - mean postings index across eight high-exposure sectors (Software Development; IT Operations & Helpdesk; Information Design & Documentation; Mathematics; Accounting; Banking & Finance; Administrative Assistance; Media & Communications) |
| `exposed_posting_index` | IN, APAC (SG proxy) | Adzuna exposed-category posting counts, indexed to 100 at first measured week (requires `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` secrets; baseline persisted in `data/adzuna_state.json`) |
| `topq_unemp_delta` | US, UK, EU, AU, IN, APAC | BLS CPS (20-24 vs 16+), ONS LMS (YBVQ 18-24 vs MGSX 16+), Eurostat `une_rt_m` (<25 vs total), ABS `LF`+`LF_AGES` (15-24 vs total; two flows - the headline LF flow has no age-band rates), ILOSTAT (IN, APAC). All seasonally adjusted where published |
| `ai_layoffs_ytd` | US | Challenger, Gray & Christmas monthly Job Cut Report - AI-cited cuts YTD; manual override via `CHALLENGER_AI_YTD_THOUSANDS` env |
| `ai_layoffs_ytd` | UK | ONS LFS redundancy level (`BEAO`, thousands, all-cause, SA) - displayed as *"Redundancies, rolling quarter (all-cause proxy)"*; no UK source attributes layoffs to AI |
| `ai_mention_postings` | US, UK, EU, AU | [Indeed Hiring Lab ai-tracker](https://github.com/hiring-lab/ai-tracker) |
| `ai_mention_postings` | IN, APAC (SG proxy) | Adzuna AI-term share of live postings (keyword proxy; looser net than Hiring Lab's curated taxonomy - labelled as such) |
| `augmentation_share` | all six | [Anthropic Economic Index](https://huggingface.co/datasets/Anthropic/EconomicIndex) (latest release resolved dynamically) |
| `ai_skill_premium` | all six | Adzuna advertised salary, AI-keyword postings vs all postings (EU = DE+FR mean, APAC = SG) - requires the Adzuna secrets |
| `hire_rate_22_25` | US | BLS CPS youth (16-24) employment level vs 2022 average (`LNS12000036`) - displayed as *"Youth employment vs 2022 (proxy)"*; the Stanford/ADP series has no machine-readable feed |
| `graduate_posting` | EU | Eurostat `edat_lfse_24` recent-graduate employment rate, YoY - displayed as *"Recent-graduate employment rate, YoY (proxy)"* |

**Proxy labelling rule:** where a KPI is fed by a proxy series, the
per-region display name is overridden (`NAME_OVERRIDES` in
`update_data.py`) *only when the proxy value was actually measured that
week*, so a carried-forward legacy value never wears a proxy label.

**Modelled (no open machine-readable source exists):** `net_creation`
everywhere (WEF Future of Jobs is biennial PDF-only - treat as a
WEF-derived projection); `ai_layoffs_ytd` for IN/EU/APAC/AU;
`hire_rate_22_25` outside the US; `graduate_posting` outside the EU.
The full review, endpoint health checks and ranked upgrade path are in
[`SOURCE_REVIEW_2026-08.md`](SOURCE_REVIEW_2026-08.md).

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

**Optional secrets** (repo → Settings → Secrets and variables → Actions):

- `BLS_API_KEY` - free at https://data.bls.gov/registrationEngine/;
  raises BLS rate limits. Works without it.
- `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` - free at
  https://developer.adzuna.com; enables the Adzuna adapters (IN/APAC
  postings + AI share, all-region salary premium). Without them those
  pairs simply stay modelled - the cron never fails on a missing key.
  ToS note: the free tier is formally a validation trial; confirm
  sustained production use with Adzuna.

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
