"""One-time backfill: thaw the frozen US AI-cited layoffs series.

Challenger changed its report phrasing with the June 2026 report ("AI has
been cited in N job cut announcements" instead of "... N cuts"), so
fetch_challenger_ai_ytd() failed silently from early July and the weekly
carry-forward froze the US ai_layoffs_ytd at the May figure (87.71k) for
2026-W27..W33. The regex is fixed in update_data.py; this script repairs
the frozen historical rows using the reports' own YTD anchors:

  June report (published ~2 Jul 2026):  YTD through June = 101.743k
    -> rows W27..W31 (written Mon 6 Jul .. Mon 3 Aug)
  July report (published ~7 Aug 2026):  YTD through July = 112.713k
    -> rows W32..W33 (written Mon 10 Aug .. Mon 17 Aug)

Rows W22..W26 keep 87.71 (the May report really was the latest available
when they were written). W10..W13 stay modelled (pre-anchor era, as
documented in backfill_real_history.py). Idempotent: only rewrites rows
whose value is 87.71 in the target weeks.
"""
import csv
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historical.csv"

ANCHORS = {  # iso_week -> corrected YTD (thousands)
    "2026-W27": 101.74, "2026-W28": 101.74, "2026-W29": 101.74,
    "2026-W30": 101.74, "2026-W31": 101.74,
    "2026-W32": 112.71, "2026-W33": 112.71,
}


def main():
    rows = list(csv.DictReader(HIST.open(encoding="utf-8")))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = 0
    for r in rows:
        if (r["region_code"] == "US" and r["kpi_id"] == "ai_layoffs_ytd"
                and r["iso_week"] in ANCHORS
                and abs(float(r["value"]) - 87.71) < 0.01):
            r["value"] = f"{ANCHORS[r['iso_week']]}"
            r["source_name"] = ("Challenger, Gray & Christmas "
                                "(AI-cited cuts YTD, backfilled)")
            r["updated_at"] = now
            n += 1
            print(f"{r['iso_week']}: 87.71 -> {r['value']}")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=rows[0].keys(), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    HIST.write_text(buf.getvalue(), encoding="utf-8")
    print(f"{n} rows corrected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
