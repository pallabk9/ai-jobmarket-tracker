# Derived metrics specification — Job Impact Index & its indexes

**Added:** 2026-08-14 · **Revised:** 2026-08-26 (Andrew review: five-index layer — AI Redundancy /
AI Advertised Job Displacement renames, AI Job Creation redefined onto measured Adzuna ad counts,
new AI New Enterprise Index; weights 25/25/20/−15/−15) ·
**Computed:** client-side in `assets/dashboard.js` (function `computeDerived`)
from `data/current.json` + `data/historical.csv`. Nothing is stored; the lineage shown in Deep mode
is the live calculation, so the dashboard and its explanation can never drift apart.

## Why derived metrics

The ten raw KPIs are precise but demand context to read. The derived layer answers the reader's
actual question — *"what net impact is AI having on this job market right now, and which way is
it moving?"* — in one number per region plus five composite indexes, while Deep mode exposes
every input, band, and weight so the translation is fully auditable.

## Naming (2026-08-20 review)

The layer was renamed for a corporate-leadership audience. Old → new:

| Old term | New term |
|---|---|
| AI Pressure Index | AI Impact Index (2026-08-20) → **Job Impact Index** (2026-08-24) |
| Job displacement (pillar) | Job Cut Index (2026-08-20) → **AI Redundancy Index** (2026-08-26) |
| Hiring pullback (pillar) | Job Opportunity Decline Index (2026-08-20) → **AI Advertised Job Displacement Index** (2026-08-26) |
| Early-career squeeze (pillar) | **Graduate Unemployment Index** |
| AI adoption pace (pillar) | **AI Adoption Index** (removed from the dashboard 2026-08-24) |
| — (new 2026-08-20) | **AI Job Creation Index** (positive direction; redefined 2026-08-26 onto measured Adzuna AI-ad counts) |
| — (new 2026-08-26) | **AI New Enterprise Index** (positive direction) |
| exposure / Observed Exposure (dashboard label) | **AI Footprint** (formal research term unchanged in citations) |
| capability gap | **Untapped AI Potential** |

## The five indexes (each scored 0–100 within-region)

| Index | Direction | Question it answers | Input KPIs (weight within index) |
|---|---|---|---|
| **AI Redundancy Index** | risk (up) | How many redundancies is AI causing? | `ai_layoffs_ytd` — 12-week flow (cumulative series) or rolling-quarter level (level series) (100%) |
| **AI Advertised Job Displacement Index** | risk (up) | Are advertised jobs disappearing? | `exposed_posting_index` level (60%), its 12-week trend (40%) |
| **Graduate Unemployment Index** | risk (up) | Are young workers feeling it first? | `topq_unemp_delta` level (50%), `hire_rate_22_25` (30%), `graduate_posting` (20%) |
| **AI Job Creation Index** | **positive (down)** | Is AI creating new jobs? | `ai_job_ads` — live AI-term ad count, indexed to its first same-basis observation (100%) |
| **AI New Enterprise Index** | **positive (down)** | Is AI spawning new businesses? | `ai_new_enterprise_jobs` level (100%) |

The **Graduate Unemployment Index is an inference indicator**: it tends to move with AI pressure,
but graduate unemployment can also reflect the wider economic cycle and other causes — the
dashboard tile carries this caveat verbatim.

## Composite

**Job Impact Index** = 0.25·AIRedundancy + 0.25·AdvertisedJobDisplacement
+ 0.20·GraduateUnemployment + **0.15·(100 − JobCreation)** + **0.15·(100 − NewEnterprise)**

Three risk indexes push the composite **up**; the two creation-side indexes are
positive-direction and enter **inverted** — strong AI job creation pulls the Job Impact Index
**down**. On the tiles both creation indexes read naturally (higher = more creation, tinted
green); the inversion happens only inside the composite, and the Deep-mode lineage prints it
explicitly.

**Creation/Enterprise overlap (documented design choice, 2026-08-26).** An advertised role at
a newly founded AI firm can appear in both creation-side indexes. The overlap is small (most
AI ads are at established employers; much new-firm employment — founders, referral hires —
never passes through a public ad) and the two deliberately measure different mechanisms:
incumbents advertising AI roles vs AI spawning new businesses. Together they cap at 30% of
the composite.

**Creation redefinition (2026-08-26).** The AI Job Creation Index previously scored the
WEF-modelled `net_creation` figure (0% measured). It now scores the **measured Adzuna count of
live job ads matching AI terms**, indexed to its first same-basis observation (launch = 100
scores 40 on the 60→160 band). Because the old modelled figure read ~80 "Strong" and the new
measured baseline launches at 40, composite levels stepped **up ~5–9 points at the cutover in
every region — a methodology step, not a worsening of conditions**. The `net_creation` KPI
remains in Deep mode powering the Net job change chart.

**The AI Adoption Index was removed from the composite on 2026-08-24** (leading indicator, not
a job outcome; it inflated adoption-heavy regions) and from the dashboard the same day; its raw
inputs stay visible as Deep-mode KPI tiles. Each tile carries a fixed plain-language
"Measures ..." definition ending with Andrew's direction line ("the higher the number ..."),
and the hero carries its own generated data narrative (change vs last month, vs the recent
average, and the biggest-moving index).

Status bands (composite and risk indexes): **0–25 Low · 25–50 Moderate · 50–70 Elevated ·
70–100 High**. The creation-side indexes use positive wording instead: **Weak · Moderate ·
Encouraging · Strong** (colour scale inverted: high = green).

In the dashboard layout the five tiles flow in Andrew's order: AI Redundancy, AI Advertised
Job Displacement, Graduate Unemployment, AI Job Creation, AI New Enterprise.

## Normalization — fixed calibration bands, not cross-region ranks

Each input maps linearly onto 0–100 between a documented floor and ceiling, clamped. Bands are
absolute and identical across regions so a region's score is comparable to *itself over time*;
cross-region comparison remains a within-country reading, consistent with the locked Anthropic
Observed Exposure methodology (no absolute cross-country footprint claims).

| Input | Floor (score 0) | Ceiling (score 100) | Orientation |
|---|---|---|---|
| `ai_layoffs_ytd` 12wk flow (cumulative basis) | 0 k / 12wk | 80 k / 12wk | more cuts now = higher |
| `ai_layoffs_ytd` quarterly level (UK level basis) | 60 k (post-1995 record low) | 250 k (severe recession) | more cuts now = higher |
| `ai_job_ads` index vs launch baseline (creation index) | 60 (collapse in AI ads) | 160 (boom vs launch) | more AI ads = higher (inverted in composite) |
| `ai_new_enterprise_jobs` (enterprise index) | 0 k (no enterprise creation) | 60 k (≈⅓ above strongest current region) | more new-firm jobs = higher (inverted in composite) |
| `graduate_posting` | +10 % YoY | −40 % YoY | fewer grad postings = higher |
| `exposed_posting_index` | 110 (boom) | 60 (bust) | fewer postings = higher |
| posting index 12wk trend | +10 pts | −10 pts | falling = higher |
| `topq_unemp_delta` | 0 pp | 10 pp | bigger youth gap = higher |
| `hire_rate_22_25` | +10 % | −30 % | falling hires = higher |

Trend inputs use the value 12 weeks before the current snapshot in `historical.csv`
(or the oldest available week when history is shorter).

**Regime-break guard (2026-08-20).** A 12-week-change input is only computed when both
endpoints share the same measurement basis (`measured` vs `modelled` in `historical.csv`).
When a KPI switches from a modelled placeholder to a measured source mid-window, differencing
across the break produces a spurious "trend" (the defect that pinned the UK Job Cut Index at
100 while ONS redundancies were falling). A mixed-basis window is treated as *input not
available* — its weight redistributes and the lineage says so — until 12 weeks of the new
basis accrue. Historical rows for series whose real history exists at the source (UK BEAO
redundancies; Indeed AI-tracker mention shares for US/UK/EU/AU; ABS youth-gap for AU; the
constant ILO annual youth-gap for IN/APAC) were backfilled with that real history
(`scripts/backfill_uk_redundancy.py`, `scripts/backfill_history_regimes.py`), so their
trends stay live.

**AI Redundancy Index (né Job Cut Index) is level-grounded (design review 2026-08-21).** The score reflects **how
much job cutting is happening right now**, and the sparkline/timeline shows that volume
changing over time; momentum lives in the trend arrow and the context line, not in the
score. (An earlier same-day iteration scored momentum instead; the design review settled on
the grounded-value reading.) The single input (`flow12w`) resolves per series basis, each
with its own fixed band:

- *cumulative YTD series* (US Challenger AI-cited cuts and the modelled regions): the
  **12-week flow** — current YTD minus 12 weeks ago, rate-scaled to 12 weeks, baseline
  walked forward to the first week on the same measurement basis (regime-break safe).
  Band `layoffs_flow` 0 → 80k (80k comfortably above the heaviest 12-week episode observed
  in the 2026 US series, ~64k, leaving headroom for worse).
- *level series* (UK: all-cause rolling-quarter redundancy level — already a per-period
  volume): the level itself. Band `layoffs_level_q` 60k → 250k (60k ≈ the post-1995 record
  low; 250k ≈ severe recession — 2009 peaked ~310k, COVID ~400k).

The tile prints the exact latest figure alongside the score — the US shows its YTD total
plus the last-12-weeks flow; the UK shows the rolling-quarter level with a rising/falling
word — so the score is always anchored to a real number.

Change log 2026-08-20: `net_creation` was promoted from a 25% input inside the old Displacement
pillar to its own positive-direction index (band recalibrated −50→+150 k for the standalone
reading); `graduate_posting` moved from Displacement into the Graduate Unemployment Index; the
old Displacement pillar became the single-input Job Cut Index. Composite weights moved from
30/25/25/20 (four pillars) to 25/25/20/15/15 (five indexes, creation inverted).

Change log 2026-08-24: the AI Adoption Index was removed from the composite (leading indicator,
not a job outcome); weights moved to 30/30/20/20 with creation still inverted, and the composite
was renamed **Job Impact Index**. Later the same day the AI Adoption Index tile was removed from
the dashboard altogether, retiring its calibration bands (mention level 0→15% and the wider
Adzuna-basis 0→40% band, mention 12-week trend −1→+3 pp, automation share 30→70%,
Untapped-AI-Potential closing 40→10 pp); its raw KPIs stay on the page in Deep mode.

Change log 2026-08-26 (Andrew review): the layer moved to **five indexes**. Renames: Job Cut →
**AI Redundancy Index**; Job Opportunity Decline → **AI Advertised Job Displacement Index**.
The AI Job Creation Index was redefined from the WEF-modelled `net_creation` figure to the
measured Adzuna `ai_job_ads` count via the new `indexvsbase` input kind (100 × current ÷ first
same-basis observation; band `ai_ads_idx` 60→160; the retired `creation_idx` band −50→+150 k
went with it). A new **AI New Enterprise Index** scores `ai_new_enterprise_jobs` — a modelled
anchor series (Stanford AI Index newly-funded startup counts × 3-year cohort × ~15 average
early headcount; see `scripts/backfill_new_indexes.py`) — on band `enterprise_idx` 0→60 k.
Weights moved from 30/30/20/20 to **25/25/20/15/15** (both creation-side indexes inverted).
Every "Measures ..." line now ends with Andrew's direction sentence, wording adjusted only
where a source cannot support a causal AI attribution (design choice: honesty over polish).

## Confidence

Every derived metric carries **confidence = Σ weight of inputs whose KPI is `measured`** for that
region, shown as a percentage on the card. An index built mostly on modelled inputs says so
up front — the badge system of the raw tiles propagates upward instead of being averaged away.
Note: since 2026-08-26 the creation index runs on the measured Adzuna `ai_job_ads` count (raising
headline confidence), while `ai_new_enterprise_jobs` is modelled everywhere, so the enterprise
index reads 0% measured by design — honesty over cosmetics.

## Missing inputs

If a KPI value is absent for a region, its weight is redistributed pro-rata across the index's
remaining inputs, and the input is listed as "not available" in the Deep-mode lineage panel.
If an entire index is unscorable, its composite weight redistributes across the remaining indexes.

## History popups

Every index tile's mini sparkline — and the Job Impact Index sparkline in the hero — is a button:
clicking it opens a full Chart.js line chart (y = the index, 0–100; x = ISO weeks) built from the
same client-side series that drew the sparkline.

## Deep mode

A global Simple/Deep toggle (persisted in `localStorage`, default Simple). Deep reveals, per index:
each input's raw value → band → normalized score → weight → contribution, the index formula, the
composite weights (including the creation inversion), and each input's measured/modelled badge and
source link — plus all ten raw KPI tiles and the full analytical charts, tables and downloads
exactly as before.
