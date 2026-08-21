# Derived metrics specification — AI Impact Index & the five indexes

**Added:** 2026-08-14 · **Revised:** 2026-08-20 (five-index composite, renamed layer) ·
**Computed:** client-side in `assets/dashboard.js` (function `computeDerived`)
from `data/current.json` + `data/historical.csv`. Nothing is stored; the lineage shown in Deep mode
is the live calculation, so the dashboard and its explanation can never drift apart.

## Why derived metrics

The ten raw KPIs are precise but demand context to read. The derived layer answers the reader's
actual question — *"what net impact is AI having on this job market right now, and which way is
it moving?"* — in one number per region plus five named indexes, while Deep mode exposes every
input, band, and weight so the translation is fully auditable.

## Naming (2026-08-20 review)

The layer was renamed for a corporate-leadership audience. Old → new:

| Old term | New term |
|---|---|
| AI Pressure Index | **AI Impact Index** |
| Job displacement (pillar) | **Job Cut Index** |
| Hiring pullback (pillar) | **Job Opportunity Decline Index** |
| Early-career squeeze (pillar) | **Graduate Unemployment Index** |
| AI adoption pace (pillar) | **AI Adoption Index** |
| — (new) | **AI Job Creation Index** (positive direction) |
| exposure / Observed Exposure (dashboard label) | **AI Footprint** (formal research term unchanged in citations) |
| capability gap | **Untapped AI Potential** |

## The five indexes (each scored 0–100 within-region)

| Index | Direction | Question it answers | Input KPIs (weight within index) |
|---|---|---|---|
| **Job Cut Index** | risk (up) | Are jobs being cut? | `ai_layoffs_ytd` pace vs 12wk ago (100%) |
| **Job Opportunity Decline Index** | risk (up) | Are exposed roles advertised less? | `exposed_posting_index` level (60%), its 12-week trend (40%) |
| **Graduate Unemployment Index** | risk (up) | Are young workers feeling it first? | `topq_unemp_delta` level (50%), `hire_rate_22_25` (30%), `graduate_posting` (20%) |
| **AI Job Creation Index** | **positive (down)** | Is AI creating new jobs? | `net_creation` level (100%) |
| **AI Adoption Index** | risk (up) | How fast is AI entering work? | `ai_mention_postings` level (40%) + 12wk trend (20%), automation share `100−augmentation_share` (20%), `capability_gap` (Untapped AI Potential) closing headroom (20%) |

The **Graduate Unemployment Index is an inference indicator**: it tends to move with AI pressure,
but graduate unemployment can also reflect the wider economic cycle and other causes — the
dashboard tile carries this caveat verbatim.

## Composite

**AI Impact Index** = 0.25·JobCut + 0.25·OpportunityDecline + 0.20·GraduateUnemployment
+ 0.15·Adoption + **0.15·(100 − JobCreation)**

Four risk indexes push the composite **up**; the AI Job Creation Index is a positive-direction
index and enters **inverted** — strong AI-attributed job creation pulls the AI Impact Index
**down**. On the tiles the creation index reads naturally (higher = more creation, tinted green);
the inversion happens only inside the composite, and the Deep-mode lineage prints it explicitly.

Status bands (composite and risk indexes): **0–25 Low · 25–50 Moderate · 50–70 Elevated ·
70–100 High**. The creation index uses positive wording instead: **Weak · Moderate ·
Encouraging · Strong** (colour scale inverted: high = green).

In the dashboard layout, the four 2×2 hook tiles are Job Cut, Job Opportunity Decline, Graduate
Unemployment and AI Job Creation; the AI Adoption Index renders as a full-width context tile
below them (it remains a weighted composite input).

## Normalization — fixed calibration bands, not cross-region ranks

Each input maps linearly onto 0–100 between a documented floor and ceiling, clamped. Bands are
absolute and identical across regions so a region's score is comparable to *itself over time*;
cross-region comparison remains a within-country reading, consistent with the locked Anthropic
Observed Exposure methodology (no absolute cross-country footprint claims).

| Input | Floor (score 0) | Ceiling (score 100) | Orientation |
|---|---|---|---|
| `ai_layoffs_ytd` 12wk flow (cumulative basis) | 0 k / 12wk | 80 k / 12wk | more cuts now = higher |
| `ai_layoffs_ytd` quarterly level (UK level basis) | 60 k (post-1995 record low) | 250 k (severe recession) | more cuts now = higher |
| `net_creation` (creation index) | −50 k (net loss) | +150 k (strong creation) | more creation = higher (inverted in composite) |
| `graduate_posting` | +10 % YoY | −40 % YoY | fewer grad postings = higher |
| `exposed_posting_index` | 110 (boom) | 60 (bust) | fewer postings = higher |
| posting index 12wk trend | +10 pts | −10 pts | falling = higher |
| `topq_unemp_delta` | 0 pp | 10 pp | bigger youth gap = higher |
| `hire_rate_22_25` | +10 % | −30 % | falling hires = higher |
| `ai_mention_postings` | 0 % | 15 % | more AI postings = higher adoption |
| mention 12wk trend | −1 pp | +3 pp | rising = higher |
| automation share (100−aug) | 30 % | 70 % | more automation = higher |
| `capability_gap` (Untapped AI Potential) | 40 pp (wide) | 10 pp (closing) | closing potential gap = higher |

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

**Job Cut Index is level-grounded (design review 2026-08-21).** The score reflects **how
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

**Basis-aware band (2026-08-20).** The Adzuna keyword AI-mention proxy (IN/APAC) is a
deliberately looser net than the Hiring Lab curated taxonomy (~20%+ vs ~5–9% shares), so
the mention *level* input uses its own calibration band (0 → 40%) whenever the KPI's source
is Adzuna. The lineage table shows which band applied.

Change log 2026-08-20: `net_creation` was promoted from a 25% input inside the old Displacement
pillar to its own positive-direction index (band recalibrated −50→+150 k for the standalone
reading); `graduate_posting` moved from Displacement into the Graduate Unemployment Index; the
old Displacement pillar became the single-input Job Cut Index. Composite weights moved from
30/25/25/20 (four pillars) to 25/25/20/15/15 (five indexes, creation inverted).

## Confidence

Every derived metric carries **confidence = Σ weight of inputs whose KPI is `measured`** for that
region, shown as a percentage on the card. An index built mostly on modelled inputs says so
up front — the badge system of the raw tiles propagates upward instead of being averaged away.
Note: `net_creation` is currently modelled everywhere (WEF-derived), so adding the creation index
lowers headline confidence by design — honesty over cosmetics.

## Missing inputs

If a KPI value is absent for a region, its weight is redistributed pro-rata across the index's
remaining inputs, and the input is listed as "not available" in the Deep-mode lineage panel.
If an entire index is unscorable, its composite weight redistributes across the remaining indexes.

## History popups

Every index tile's mini sparkline — and the AI Impact Index sparkline in the hero — is a button:
clicking it opens a full Chart.js line chart (y = the index, 0–100; x = ISO weeks) built from the
same client-side series that drew the sparkline.

## Deep mode

A global Simple/Deep toggle (persisted in `localStorage`, default Simple). Deep reveals, per index:
each input's raw value → band → normalized score → weight → contribution, the index formula, the
composite weights (including the creation inversion), and each input's measured/modelled badge and
source link — plus all ten raw KPI tiles and the full analytical charts, tables and downloads
exactly as before.
