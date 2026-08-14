# Derived metrics specification — AI Pressure Index & pillar signals

**Added:** 2026-08-14 · **Computed:** client-side in `assets/dashboard.js` (function `computeDerived`)
from `data/current.json` + `data/historical.csv`. Nothing is stored; the lineage shown in Deep mode
is the live calculation, so the dashboard and its explanation can never drift apart.

## Why derived metrics

The ten raw KPIs are precise but demand context to read. The derived layer answers the reader's
actual question — *"how much pressure is AI putting on this job market right now, and which way is
it moving?"* — in one number per region plus four named pillars, while Deep mode exposes every
input, band, and weight so the translation is fully auditable.

## The four pillars (each scored 0–100 within-region)

| Pillar | Question it answers | Input KPIs (weight within pillar) |
|---|---|---|
| **Displacement** | Are jobs being cut? | `ai_layoffs_ytd` pace vs 12wk ago (50%), `net_creation` (25%), `graduate_posting` (25%) |
| **Hiring pullback** | Are exposed roles being hired less? | `exposed_posting_index` level (60%), its 12-week trend (40%) |
| **Early-career squeeze** | Are young workers feeling it first? | `topq_unemp_delta` level (60%), `hire_rate_22_25` (40%) |
| **AI adoption** | How fast is AI entering work? | `ai_mention_postings` level (40%) + 12wk trend (20%), automation share `100−augmentation_share` (20%), `capability_gap` closing headroom (20%) |

## Composite

**AI Pressure Index** = 0.30·Displacement + 0.25·Hiring pullback + 0.25·Early-career + 0.20·Adoption

Status bands: **0–25 Low · 25–50 Moderate · 50–70 Elevated · 70–100 High**.

## Normalization — fixed calibration bands, not cross-region ranks

Each input maps linearly onto 0–100 between a documented floor and ceiling, clamped. Bands are
absolute and identical across regions so a region's score is comparable to *itself over time*;
cross-region comparison remains a within-country reading, consistent with the locked Anthropic
Observed Exposure methodology (no absolute cross-country exposure claims).

| Input | Floor (score 0) | Ceiling (score 100) | Orientation |
|---|---|---|---|
| `ai_layoffs_ytd` 12wk pace | 0 k roles / 12wk | 30 k roles / 12wk | more cuts = higher |
| `net_creation` | +50 k (net creation) | −50 k (net loss) | net loss = higher |
| `graduate_posting` | +10 % YoY | −40 % YoY | fewer grad postings = higher |
| `exposed_posting_index` | 110 (boom) | 60 (bust) | fewer postings = higher |
| posting index 12wk trend | +10 pts | −10 pts | falling = higher |
| `topq_unemp_delta` | 0 pp | 10 pp | bigger youth gap = higher |
| `hire_rate_22_25` | +10 % | −30 % | falling hires = higher |
| `ai_mention_postings` | 0 % | 15 % | more AI postings = higher adoption |
| mention 12wk trend | −1 pp | +3 pp | rising = higher |
| automation share (100−aug) | 30 % | 70 % | more automation = higher |
| `capability_gap` | 40 pp (wide gap) | 10 pp (gap closing) | closing gap = higher |

Trend inputs use the value 12 weeks before the current snapshot in `historical.csv`
(or the oldest available week when history is shorter).

## Confidence

Every derived metric carries **confidence = Σ weight of inputs whose KPI is `measured`** for that
region, shown as a percentage on the card. A pillar built mostly on modelled inputs says so
up front — the badge system of the raw tiles propagates upward instead of being averaged away.

## Missing inputs

If a KPI value is absent for a region, its weight is redistributed pro-rata across the pillar's
remaining inputs, and the input is listed as "not available" in the Deep-mode lineage panel.

## Deep mode

A global Simple/Deep toggle (persisted in `localStorage`, default Simple). Deep reveals, per pillar:
each input's raw value → band → normalized score → weight → contribution, the pillar formula, the
composite weights, and each input's measured/modelled badge and source link — plus all ten raw KPI
tiles and the full analytical charts, tables and downloads exactly as before.
