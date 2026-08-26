# AI Job Market Impact Tracker

A live dashboard tracking AI's impact on labour markets across six regions, grounded in the Anthropic Observed Exposure methodology (Massenkoff & McCrory, March 2026).

**Live site:** https://ai-jobmarket-tracker.netlify.app/

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

## Simple / Deep view and derived metrics (2026-08-14; Job Impact Index five-index composite 2026-08-26)

The dashboard has two reading levels, toggled at the top of the Live
dashboard section (persisted per browser):

- **Simple** (default): one **Job Impact Index** (0-100) per region plus
  five plain-language indexes - *AI Redundancy Index*, *AI Advertised Job
  Displacement Index*, *Graduate Unemployment Index* (an inference
  indicator, caveated on the tile), *AI Job Creation Index* (newly
  advertised AI jobs) and *AI New Enterprise Index* (employment at new AI
  businesses; both positive direction - they pull the composite **down**;
  enter inverted) - each with a status word, a "Measures ..." definition
  ending in a direction line, month-over-month delta, a clickable
  sparkline (opens a full history chart), and a "% measured" confidence
  chip. A data-provenance narrative
  at the top of the page explains the authoritative-sources /
  measured-vs-modelled contract.
- **Deep**: everything under the hood - all ten raw KPI tiles with
  measured/modelled badges, the full analytical charts, and an "Under the
  hood" lineage panel on every index card showing each input's raw value
  → calibration band → normalized score → weight → contribution, with its
  source link and provenance badge.

Composite (**Job Impact Index**; five-index layer per the Andrew review,
2026-08-26): 25% AI Redundancy + 25% Advertised Job Displacement + 20%
Graduate Unemployment + 15% × (100 − Job Creation) + 15% × (100 − New
Enterprise). The AI Job Creation Index is measured — the live Adzuna
count of job ads matching AI terms, indexed to its launch baseline — and
the AI New Enterprise Index is a modelled anchor series (Stanford AI
Index startup counts × cohort × average early headcount). The two
creation-side indexes overlap only slightly (an advertised role at a new
AI firm can appear in both) — a documented design choice, as they track
different mechanisms. The AI Adoption Index was removed on 2026-08-24
(leading indicator, not a job outcome); its raw signals stay visible as
KPI tiles in Deep view. Every tile carries a plain-language
"Measures ..." definition, and the hero carries its own generated data
narrative.

**Terminology (2026-08-20):** the dashboard's plain-language term for
Observed Exposure is now **AI Footprint** (the formal research term is
kept in citations), and the capability gap is now **Untapped AI
Potential**. Old names appear in the glossary for continuity.

Derived metrics are computed **client-side** in `assets/dashboard.js` from
`data/current.json` + `data/historical.csv` - the lineage shown *is* the
calculation, so dashboard and documentation cannot drift apart. Formulas,
calibration bands and weights are specified in
[`DERIVED_METRICS.md`](DERIVED_METRICS.md). Scores compare a region to
itself over time; they are not cross-country footprint rankings (consistent
with the locked Observed Exposure methodology).

## Sector pulse (Phase 1 2026-08-17; Phase 2 same day; power & utilities 2026-08-20)

AI impact by sector — banking, insurance, IT & software, telecom & media,
manufacturing, healthcare, retail, professional services, education,
government, **power & utilities** — for **all six regions**. Power &
utilities spans ISIC sections D+E (merged in section-level matrices; the
concordance marks it `D+E`): UK employment/vacancies sum ONS CDIDs
JWR8+JWR9 / JP9J+JP9K, EU employment sums NACE D+E, AU uses ANZSIC
division D, US layoffs sum Challenger's Energy + Utility rows, EU layoffs
sum ERM's Electricity + Water/Waste sectors. Indeed and Singapore MOM have
no utilities category, so those signals show as explicit "not published"
stubs with weight redistribution. Phase 2 additions: India and APAC
exposure via ILOSTAT ISCO×ISIC annual matrices (APAC pools SGP+JPN+KOR);
quarterly ILO sector employment (annual fallback where quarterly carries
aggregates only); Singapore MOM vacancies by industry as the APAC proxy
demand market (with a real telecom/IT split); Naukri JobSpeak hiring
momentum (% YoY, conservatively text-parsed) filling India's posting slot
in the pressure blend; Adzuna category postings activate for IN/APAC when
the API keys are configured.

- **Sector AI Footprint Score** (formerly Sector AI Exposure Score) = 100 ×
  employment-share-weighted mean of Anthropic Observed Exposure across each
  sector's occupation mix, displayed as a within-region index (top sector =
  100; cross-region comparison is deliberately not supported, per the
  locked methodology).
  Occupation×industry matrices: BLS OEWS (US, fine), ONS ad-hoc 3136 ×
  AWA UK model (UK, fine), Eurostat `lfsq_eisn2` (EU, coarse ISCO majors),
  ILOSTAT `EMP_TEMP_ECO_OCU` (AU, IN, APAC pooled - coarse). Built quarterly by
  `scripts/build_sector_model.py` (`build-sector-model.yml`).
- **Weekly signals** per sector via `scripts/update_sectors.py` in the
  Monday cron: Indeed Hiring Lab sector postings (US/GB/DE+FR/AU, weekly),
  ONS JOBS02 + VACS02 (UK), Eurostat `lfsq_egan2`/`lfsq_egan22d` (incl.
  the K64 banking / K65 insurance split) + `jvs_q_nace2` (EU), ABS Labour
  Account + Job Vacancies (AU), BLS CES (US). Any fetch failure leaves
  the previous signal untouched.
- **Sector Pressure** (dashboard, client-side): 45% AI Footprint index + 25%
  posting trend / hiring momentum + 15% vacancy/employment momentum + 15%
  announced layoffs as a share of sector workforce (US: Challenger's
  30-industry monthly table, PDF-parsed; EU: Eurofound ERM announced job
  losses, trailing 12 months, EU27). Fixed bands; missing components have
  their weight redistributed pro-rata, and the Deep-view lineage names
  every input used and every input missing.
- Data: `data/sectors.json` (current state) + `data/sector_series.csv`
  (append-only archive). Taxonomy mapping: `model/sector_concordance.csv`.
  Research + phase plan: `SECTOR_RESEARCH_2026-08.md`.

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
- 2026-08-20: UK `ai_layoffs_ytd` rows in `historical.csv` (W10-W32)
  were backfilled with the real ONS BEAO redundancy series
  (`scripts/backfill_uk_redundancy.py`). The old modelled placeholder
  (~4k, a different definition) sat next to the measured BEAO proxy
  (~108k) that started in W33, so the Job Cut Index's 12-week change
  differenced across the regime break and pinned at 100 while actual UK
  redundancies were falling (FEB 126 -> MAY 106). Snapshots untouched;
  the derived layer reads `historical.csv`. Same repair class as the
  June backfill.
- 2026-08-20 (full-number audit, same day): the same regime-break class
  was found and repaired for `ai_mention_postings` (US/UK/EU/AU -
  backfilled from the Indeed AI-tracker's real history) and
  `topq_unemp_delta` (AU from ABS history; IN/APAC from the constant
  ILO annual value) via `scripts/backfill_history_regimes.py`; the
  dashboard also gained a structural guard - 12-week-change inputs are
  skipped (weight redistributed) whenever the window mixes modelled and
  measured rows - plus an Adzuna-basis calibration band for the looser
  IN/APAC keyword mention proxy (spec: DERIVED_METRICS.md). Three
  adapter bugs fixed the same day: the OEWS series id used a 6-zero
  area code (24-char ids -> empty US matrix in the quarterly CI build;
  now 7 zeros/25 chars), Adzuna's `marketing-jobs` category tag does
  not exist (`pr-advertising-marketing-jobs` does), and Adzuna's
  `/history` endpoint rejects `results_per_page` (now only sent on
  search paths). Salary-premium coverage note: Adzuna publishes
  AI-filtered salary history only for US and GB, so `ai_skill_premium`
  is measured there and stays modelled elsewhere.
- `current.json` is refreshed in place by manual workflow runs
  (FORCE_REFRESH), while `historical.csv` keeps the values recorded at
  each Monday snapshot; small deltas between the two for the same week
  are expected until the next Monday run.
- 2026-08-21: the Job Cut Index was redesigned as **level-grounded**
  (design review): the score reflects the current volume of job cutting
  - the 12-week flow for cumulative YTD series (band 0-80k), the
  rolling-quarter level itself for the UK's level series (band 60-250k,
  anchored to the post-1995 record low and severe-recession territory) -
  and the sparkline shows that volume over time. Momentum lives in the
  trend arrow and the tile's context line, which always prints the exact
  latest figure. (A same-day momentum-gauge iteration was superseded by
  this design.)
- 2026-08-21: Challenger changed its report phrasing in June ("cited in
  N *job cut announcements*"), silently freezing the US `ai_layoffs_ytd`
  parse at the May figure (87.71k) for 12 weeks of carry-forward. The
  patterns now accept both phrasings, and W27-W33 were corrected from
  the June/July reports' own YTD anchors (101.74k / 112.71k) by
  `scripts/backfill_us_challenger.py`.

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
