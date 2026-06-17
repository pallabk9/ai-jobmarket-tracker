# US occupation model — O*NET + BLS OES

This is the first non-UK regional build. It's the easiest region because
**O*NET publishes task-level data**, so the one hand-estimated step in the UK
model (per-occupation task-time allocation) is derived directly instead.

## Inputs

| Component | Source | File |
|---|---|---|
| Occupation taxonomy | SOC 2018 (6-digit), via O*NET-SOC | O*NET `Occupation Data.txt` |
| Task-time allocation | O*NET 41 Generalized Work Activities, **Importance** scores | O*NET `Work Activities.txt` → `gwa_task_crosswalk.csv` |
| Employment weights | BLS OES national, detailed occupations | `oesm{YY}nat.zip` → `national_M{YYYY}_dl.xlsx` |
| Adoption / amplification | by SOC major group | `soc_major_groups.csv` |

The 18 task-susceptibility scores come from `../task_scores.csv` (region-agnostic).

## Method

For each occupation, each O*NET work activity's importance `IM` (1–5) is turned
into a relevance weight `(IM − 1)²`, mapped to one of the 18 task categories via
`gwa_task_crosswalk.csv`, and normalised across the 18 tasks to a time-allocation
proxy summing to 100%. Then, exactly as the UK model:

```
raw exposure   = Σ(task% × susceptibility)
practical      = raw × adoption_discount        (by SOC major group)
hours freed    = practical × 40h week ; FTE = hours × emp / 40
combined hours = hours × amplification_multiplier
```

**Why (IM − 1)²:** raw O*NET importance is too flat — every occupation rates
most activities 2–4, so exposures compress into a narrow band. The transform
zeroes "not important" activities and concentrates weight on core ones, which
restores a realistic spread (validated on O*NET 30.3: ~0.47 for manual/physical
occupations up to ~0.86 for analytical ones; software developers ≈ 0.79,
data-entry keyers ≈ 0.78, registered nurses ≈ 0.66, carpenters ≈ 0.62).

**Comparability:** US task weights are O*NET-importance-derived; the UK model
uses hand-estimated time shares. Rankings and within-region gaps are comparable;
absolute US-vs-UK levels are not. The dashboard labels both as `modelled`.

## Run it

Needs network to O*NET and BLS (a firewalled sandbox can't reach them; a normal
machine or GitHub Actions can).

```bash
pip install openpyxl
python3 model/regional_build/us/build_us_from_onet.py
```

Outputs `data/us_occupations.json`, rewrites `model/regional_build/regions/US_occupations.csv`,
and patches the US `gap_chart` + `capability_gap` in `data/current.json`. The
dashboard already renders the top-10 chart and the full-screen 894-occupation
popup for any region whose `gap_chart` carries a `detail` field — no front-end
change needed.

Offline / testing: point the loaders at local files with `ONET_WA_FILE`,
`ONET_OCC_FILE`, `BLS_OES_XLSX`. Downloads are cached in `data_cache/`
(git-ignored); delete it to force a fresh pull.

## Automation

`.github/workflows/build-us-model.yml` runs this quarterly (and on manual
dispatch) in CI, where O*NET and BLS are reachable, and commits the refreshed
`us_occupations.json` + `current.json`. Bump `ONET_VER` and `BLS_OES_ZIP` in the
workflow when O*NET ships a new database or the OES year rolls over.
