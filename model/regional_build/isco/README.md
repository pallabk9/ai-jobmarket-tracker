# EU / India / Australia / APAC — O*NET-via-ISCO task-time models

These regions reuse the US O*NET task profiles (task content is broadly universal),
mapped to **ISCO-08** and weighted by each region's own employment. The builder is
`../build_region_from_onet.py`; the CI workflow is `.github/workflows/build-regions-model.yml`.

O*NET is fetched at run time (reachable from CI). Two inputs are **committed data**
(static or annual), because their sources block cloud/CI IPs or need manual export:

## 1. `soc_isco_crosswalk.csv` — shared, one-off

Maps each 6-digit US SOC to its ISCO-08 2-digit sub-major group. Columns:
`soc_code, isco2_code, isco2_name`. A SOC may map to more than one ISCO (one row each).

Source: BLS "ISCO-08 x SOC" crosswalk (`bls.gov/soc/ISCO_SOC_Crosswalk.xls`) or the
IBS "O*NET-SOC to ISCO" crosswalk. Download once, reduce to the three columns, commit.
Static — only changes when SOC or ISCO is revised (years apart).

## 2. `<REGION>_employment.csv` — per region, annual

Employment by ISCO-08 2-digit for that region. Columns:
`isco2_code, isco2_name, employment`.

Source: **ILOSTAT** indicator `EMP_TEMP_SEX_OCU_NB` (employment by sex and
occupation), classification ISCO-08 2-digit, sex = Total, latest year. Export per
country/region from ilostat.ilo.org (or its bulk CSV/SDMX), keep the three columns,
commit. EU = EU-27 aggregate; APAC = sum of the chosen economies (e.g. SG, JP, KR).

## Run

```bash
python3 model/regional_build/build_region_from_onet.py EU   # or IN / AU / APAC
```

Writes `data/<region>_occupations.json` and patches that region's `gap_chart` +
`capability_gap` in `data/current.json`. The dashboard already renders the top chart
and the full-screen popup for any region whose `gap_chart` has a `detail` field — no
front-end change needed.

The CI workflow builds all four; regions whose two CSVs aren't populated yet are
skipped with a warning, so you can fill them in one at a time.

## Granularity & comparability

Rows are ISCO-08 2-digit sub-major groups (~40), grouped by ISCO 1-digit major group
(10) for the chart — coarser than the US (774 detailed SOC occupations) but real and
consistent across regions. Task weights are O*NET-derived via the same (IM-1)² transform
as the US build; adoption/amplification are by ISCO major group (`isco_major_groups.csv`).
As with US vs UK, rankings and within-region gaps are comparable across regions;
absolute levels are not, and all are labelled `modelled`.
