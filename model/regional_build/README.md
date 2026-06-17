# Regional rebuild framework — AWA AI occupation impact model

The UK model (`netlify-site/model/AWA_AI_412_Occupations.xlsx`) is taxonomy-specific:
it is keyed to **UK SOC 2020** occupations and **ONS** employment. The *methodology*
ports to any region; the *data* does not. This folder is the machinery to rebuild it
for the other five regions without re-deriving the maths.

## What transfers unchanged (already here)

- **`task_scores.csv`** — the 18 task-category AI-susceptibility scores (May 2026 frontier).
  These are capability-based, so they are region-agnostic. Do **not** edit per region;
  they change only on a frontier recalibration (the quarterly cadence).
- **`amplification_multipliers.csv`** — the eight 1.0×–2.5× capability tiers by occupation family.
- **`adoption_discounts.csv`** — the 0.48–0.60 sector adoption-discount bands.

## What must be rebuilt per region (the four components)

For each region you populate one file, `regions/<REGION>_occupations.csv`
(copy of `templates/region_occupations_TEMPLATE.csv`), supplying four things:

1. **Occupation-taxonomy crosswalk** — the region's occupation list (`occ_code`,
   `occ_title`, `group_code`, `group_name`). Map it to the 18 task categories.
2. **Per-occupation task-time allocations** — `T01`…`T18`, the % of the working week
   each occupation spends in each task category. Must sum to 100 per row.
3. **National employment weights** — `employment`, workers per occupation, from the
   national statistics agency.
4. **Region-specific adoption discounts** — `adoption_discount` per occupation (and the
   `amplification_multiplier` tier), reflecting that region's deployment pace.

`regions/UK_occupations.csv` is included as a **worked reference**: a fully populated
input that reproduces the published UK model to within rounding (validated:
max raw-exposure difference 0.0).

## Per-region data sources

| Region | Occupation taxonomy | Task-time source | Employment | Difficulty |
|---|---|---|---|---|
| **US** | SOC 2018 / O*NET-SOC | **O*NET** Work Activities + DWA time data (native, automates most of step 2) | BLS OES (May series) | Easiest |
| **EU** | ISCO-08 / ESCO | ESCO essential activities; allocate via ISCO↔O*NET crosswalk | Eurostat `lfsa_egais` | Medium |
| **AU** | ANZSCO | O*NET crosswalk (ANZSCO↔ISCO↔O*NET) | ABS Labour Force by occupation | Medium |
| **India** | NCO-2015 | sparse native task data; derive via NCO↔ISCO↔O*NET | PLFS (MoSPI) | Hard |
| **APAC** | mixed (SG SSOC, JP, KR…) | ISCO crosswalk per country | national agencies | Hardest |

US is the logical first build: O*NET publishes task-level time data, so step 2 is largely
automatable rather than hand-estimated.

## Build a region

```bash
cd netlify-site/model/regional_build
python3 build_region.py US            # reads regions/US_occupations.csv
# -> writes netlify-site/data/us_occupations.json and prints the capability gap
```

`build_region.py` is the same engine as the UK builder, taxonomy-agnostic. It computes,
per occupation: raw exposure = Σ(task-time% × susceptibility); practical impact =
raw × adoption discount; hours freed = practical × 37-hour week; FTE capacity;
amplification; combined hours. It **invents nothing** — an empty or placeholder input
fails loudly instead of emitting fabricated numbers.

## Wire a built region into the dashboard

After `data/<region>_occupations.json` exists, patch that region's `gap_chart` and
`capability_gap` in `data/current.json` exactly as `scripts/build_uk_occupations.py`
does for the UK (set `gap_chart.cats/names/theoretical/observed` from the groups,
`detail="<region>_occupations.json"`). The front-end (`assets/dashboard.js`) already
opens the click-through occupation modal for any region whose `gap_chart` carries a
`detail` field — no JS change needed per region.

## Update cadence

Same as UK: **quarterly** frontier-score recalibration (edit `task_scores.csv` once;
it feeds every region) plus an **annual** employment refresh (re-pull each region's
employment weights). The scheduled task `uk-occupation-model-recalibration` covers the
UK; clone it per region once a region is populated.
