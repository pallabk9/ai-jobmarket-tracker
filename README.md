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

## Wiring real data sources

`scripts/update_data.py` ships with a v1 deterministic-drift adapter for every KPI so the cron runs end-to-end out of the box. To replace a stub with a real adapter:

1. Open `scripts/update_data.py`
2. Find the `ADAPTERS` dict near the top
3. Write a function `def my_adapter(region, kpi_id): ...` that returns a float
4. Replace the entry: `ADAPTERS["ai_layoffs_ytd"] = my_adapter`
5. If the adapter needs an API key, put it in **Settings → Secrets and variables → Actions** on GitHub, then read it in Python via `os.environ["MY_KEY"]`
6. In `.github/workflows/weekly-update.yml`, expose the secret to the job by adding to the `env:` of the `Refresh weekly data` step

Suggested first three adapters to wire (in priority order):

- `ai_layoffs_ytd` → Layoffs.fyi public CSV
- `ai_mention_postings` → Indeed Hiring Lab API
- `topq_unemp_delta` → BLS LAUS / CPS API

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
