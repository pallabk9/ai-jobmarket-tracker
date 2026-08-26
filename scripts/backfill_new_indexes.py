#!/usr/bin/env python3
"""One-time seed for the two creation-side KPIs added in the Andrew review of
2026-08-26 (five-index Job Impact layer):

* ``ai_job_ads`` - live job ads matching the Adzuna AI term set, thousands,
  summed across each region's Adzuna markets (US, GB, IN, DE+FR, SG, AU).
  MEASURED when ADZUNA_APP_ID / ADZUNA_APP_KEY are present; the weekly
  pipeline keeps it refreshed thereafter (adapter `_adapter_adzuna_ai_ads`).
  History accrues from this seed onward; the AI Job Creation Index scores the
  count indexed to its first same-basis observation (=100 at launch).

* ``ai_new_enterprise_jobs`` - people employed in businesses founded because
  of AI. No statistics agency publishes this anywhere, so it ships as an
  honestly-badged MODELLED anchor series (carried forward weekly), derived:

      anchor = newly-funded AI startups per year (Stanford AI Index 2025
               geography counts: US ~1,000; EU ~400; UK ~180; IN ~250;
               APAC(SG/JP/KR) ~250; AU ~60)
             x 3-year founding cohort still operating
             x ~15 average early-stage headcount (OECD.AI / Crunchbase
               early-stage medians 10-20)

  giving (k roles): US 45.0, UK 8.0, EU 18.0, IN 12.0, APAC 11.0, AU 2.7.
  Unfunded formations are deliberately excluded (conservative).

Idempotent: re-running replaces the seeded values instead of duplicating rows.
Writes data/current.json + appends rows to data/historical.csv at the latest
week already present in the CSV (no partial mid-week column is created).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

from update_data import (  # noqa: E402
    ADZUNA_CC, ADZUNA_AI_TERMS, REGIONS, REGION_LABEL,
    _adzuna_count, _adapter_adzuna_ai_ads,
)

ENTERPRISE_ANCHORS = {  # k roles - derivation in module docstring
    "US": 45.0, "UK": 8.0, "IN": 12.0, "EU": 18.0, "APAC": 11.0, "AU": 2.7,
}

KPI_META = {
    "ai_job_ads": dict(
        name="Advertised AI-skill jobs (live ads)", unit="k ads", direction="down",
        source_mod="Adzuna live job-ad counts",
        url="https://developer.adzuna.com/"),
    "ai_new_enterprise_jobs": dict(
        name="Employment in new AI businesses", unit="k roles", direction="down",
        source_mod="AWA model · Stanford AI Index + OECD.AI anchors",
        url="https://hai.stanford.edu/ai-index"),
}


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = json.loads((DATA / "current.json").read_text())

    # -- resolve values ------------------------------------------------
    values: dict[tuple[str, str], tuple[float, str, str, str]] = {}
    have_key = bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))
    for region in REGIONS:
        if have_key:
            try:
                v, src, url = _adapter_adzuna_ai_ads(region, now[:10])
                values[("ai_job_ads", region)] = (v, src, url, "measured")
            except Exception as exc:  # noqa: BLE001
                print(f"ai_job_ads/{region}: {exc} - skipping (no fake value seeded)")
        m = KPI_META["ai_new_enterprise_jobs"]
        values[("ai_new_enterprise_jobs", region)] = (
            ENTERPRISE_ANCHORS[region], m["source_mod"], m["url"], "modelled")

    if not have_key:
        print("ADZUNA_APP_ID/KEY not set: ai_job_ads not seeded (CI will fill it)")

    # -- current.json --------------------------------------------------
    for (kpi, region), (v, src, url, meas) in values.items():
        m = KPI_META[kpi]
        cur["regions"][region]["kpis"][kpi] = {
            "name": m["name"], "value": v, "unit": m["unit"],
            "direction": m["direction"], "source": src, "source_url": url,
            "measurement": meas,
        }
    cur["backfilled_at"] = now
    (DATA / "current.json").write_text(json.dumps(cur, indent=1) + "\n")

    # -- historical.csv (at the latest week already present) -----------
    hist_path = DATA / "historical.csv"
    with hist_path.open() as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = list(rows[0].keys())
    latest_week = max(r["iso_week"] for r in rows)
    week_ending = next(r["week_ending"] for r in rows if r["iso_week"] == latest_week)

    seeded_ids = {k for k, _ in values}
    rows = [r for r in rows if not (r["iso_week"] == latest_week and r["kpi_id"] in seeded_ids)]
    for (kpi, region), (v, src, url, meas) in sorted(values.items()):
        m = KPI_META[kpi]
        rows.append({
            "iso_week": latest_week, "week_ending": week_ending,
            "region_code": region, "region": REGION_LABEL[region],
            "kpi_id": kpi, "kpi_name": m["name"], "value": v,
            "unit": m["unit"], "direction": m["direction"],
            "source_name": src, "source_url": url,
            "measurement": meas, "updated_at": now,
        })
    rows.sort(key=lambda r: (r["iso_week"], r["region_code"], r["kpi_id"]))
    with hist_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Seeded {len(values)} (kpi, region) pairs at {latest_week}:")
    for (kpi, region), (v, _, _, meas) in sorted(values.items()):
        print(f"  {kpi:24s} {region:4s} {v:>8.2f}  [{meas}]")


if __name__ == "__main__":
    main()
