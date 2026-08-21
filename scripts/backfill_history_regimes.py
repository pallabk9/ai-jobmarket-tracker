"""One-time backfill: align pre-wiring history with each measured basis.

Found by the 2026-08-20 audit (after the UK redundancy fix exposed the
pattern): several KPIs switched from a modelled placeholder to a measured
source mid-series, leaving historical.csv rows on the old basis. Level
inputs then show spurious sparkline steps, and 12-week-change inputs
difference across the break (the exact defect the UK Job Cut Index had).

Repairs (only rows still marked modelled are touched - idempotent):

1. ai_mention_postings US/UK/EU/AU (modelled W10-W23, measured W24+):
   replaced with the real Indeed Hiring Lab AI-tracker value at each
   week's date - the adapter already resolves any historical date, so
   this is exact source history.
2. topq_unemp_delta AU (modelled before W33): replaced with the real
   ABS youth-minus-total unemployment gap for the month available at
   each week (ABS LFS month M taken as available from day 18 of M+1).
3. topq_unemp_delta IN/APAC (modelled before W24): the wired ILOSTAT
   series is annual, so the measured value is constant within the year;
   history is set to that same annual value - exactly what the adapter
   returns for any date this year.

Each backfilled row inherits name/source/unit from the region's first
measured row (with ", backfilled" appended to the source), and is marked
measured. Same repair class as the 2026-06-10 and UK-redundancy
backfills; snapshots untouched.

Run:  python3 scripts/backfill_history_regimes.py
"""
import csv
import io
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_data as ud  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historical.csv"


def au_gap_by_availability():
    """[(available_from, gap_pp)] from the ABS youth/total rate series."""
    series = ud.fetch_abs_unemp()
    out = []
    for m, tot in sorted(series["total"].items()):
        y = series["youth"].get(m)
        if y is None:
            continue
        yy, mm = int(m[:4]), int(m[5:7])
        ay, am = (yy + 1, 1) if mm == 12 else (yy, mm + 1)
        out.append((date(ay, am, 18), round(y - tot, 2)))
    return out


def main():
    rows = list(csv.DictReader(HIST.open(encoding="utf-8")))
    fields = rows[0].keys()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # template = first measured row per (kpi, region)
    tmpl = {}
    for r in rows:
        key = (r["kpi_id"], r["region_code"])
        if r["measurement"] == "measured" and key not in tmpl:
            tmpl[key] = r

    au_gaps = au_gap_by_availability()
    n = 0
    for r in rows:
        key = (r["kpi_id"], r["region_code"])
        if r["measurement"] != "modelled" or key not in tmpl:
            continue
        kpi, reg = key
        wk_end = date.fromisoformat(r["week_ending"])
        value = None
        if kpi == "ai_mention_postings" and reg in ("US", "UK", "EU", "AU"):
            try:
                value, _, _ = ud._adapter_ai_mention(reg, r["week_ending"])
            except Exception:
                continue
        elif kpi == "topq_unemp_delta" and reg == "AU":
            avail = [(af, v) for af, v in au_gaps if af <= wk_end]
            if not avail:
                continue
            value = avail[-1][1]
        elif kpi == "topq_unemp_delta" and reg in ("IN", "APAC"):
            value = float(tmpl[key]["value"])   # annual series: constant
        if value is None:
            continue
        t = tmpl[key]
        r["value"] = f"{value}"
        r["kpi_name"] = t["kpi_name"]
        r["unit"] = t["unit"]
        r["direction"] = t["direction"]
        r["source_name"] = t["source_name"].split(", backfilled")[0] + ", backfilled"
        r["source_url"] = t["source_url"]
        r["measurement"] = "measured"
        r["updated_at"] = now
        n += 1
        print(f"{r['iso_week']} {reg} {kpi}: -> {value}")

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    HIST.write_text(buf.getvalue(), encoding="utf-8")
    print(f"{n} rows backfilled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
