"""One-time backfill: UK ai_layoffs_ytd history -> real ONS BEAO series.

Problem (found 2026-08-20, user report): the UK Job Cut Index read 100
while the underlying ONS series was falling. Cause: a series-regime break.
Until 2026-W32 the UK ai_layoffs_ytd rows in historical.csv carried the
old *modelled* "AI-attributed layoffs (YTD)" placeholder (~4k); from
2026-W33 the weekly cron writes the *measured* ONS BEAO proxy
("LFS: ILO redundancy level (thousands): UK: All: SA", ~108k) - a
different definition and scale. The Job Cut Index input is the 12-week
change, so it differenced across the break: 108.0 - 4.0 = +104k against
a 0->30k band -> clamped to 100. The real BEAO series was *falling*
(2026: FEB 126 -> MAR 113 -> APR 108 -> MAY 106).

Fix: replace the modelled UK ai_layoffs_ytd rows (before the first
measured week) with the BEAO value that was actually published at each
snapshot date, so the 12-week change is computed on one consistent,
measured series. Same class of repair as the 2026-06-10 real-history
backfill (synthetic seed data replaced by the wired source's history);
snapshots are left untouched - the derived layer reads historical.csv.

Publication-lag model (empirical anchors): a BEAO month labelled M first
appears in the ONS LMS release in month M+3 (e.g. "2026 APR" was the
latest point the 2026-08-17 cron saw; "2026 MAY" appeared with the
~19 Aug release). We treat month M as available from day 18 of M+3.
This reproduces the cron's view exactly at the W33 boundary
(backfilled W30-W32 = 108.0 = measured W33).

Run:  python3 scripts/backfill_uk_redundancy.py
Safe to re-run (idempotent: only rewrites rows still marked modelled).
"""
import csv
import io
import json
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historical.csv"
BEAO_URL = ("https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/"
            "redundancies/timeseries/beao/lms")

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def fetch_beao():
    """[(label, available_from, value)] oldest->newest from the ONS API."""
    req = urllib.request.Request(BEAO_URL + "/data", headers={
        "User-Agent": "ai-jobmarket-tracker (research; github.com/pallabk9)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        js = json.load(r)
    out = []
    for m in js.get("months", []):
        y, mon = m["date"].split()
        yy, mm = int(y), MONTHS[mon.upper()[:3]]
        # available from day 18 of month M+3 (see module docstring)
        ay, am = (yy + 1, mm - 9) if mm > 9 else (yy, mm + 3)
        out.append((m["date"], date(ay, am, 18), float(m["value"])))
    return out


def main():
    beao = fetch_beao()
    rows = list(csv.DictReader(HIST.open(encoding="utf-8")))
    fields = rows[0].keys()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = []
    for r in rows:
        if (r["region_code"] != "UK" or r["kpi_id"] != "ai_layoffs_ytd"
                or r["measurement"] != "modelled"):
            continue
        wk_end = date.fromisoformat(r["week_ending"])
        avail = [(lbl, v) for lbl, af, v in beao if af <= wk_end]
        if not avail:
            continue
        label, value = avail[-1]
        changed.append((r["iso_week"], r["value"], value, label))
        r["value"] = f"{value:.1f}"
        r["kpi_name"] = "Redundancies, rolling quarter (all-cause proxy)"
        r["source_name"] = (f"ONS LFS redundancies (all-cause, thousands, SA, "
                            f"{label}, backfilled)")
        r["source_url"] = BEAO_URL
        r["measurement"] = "measured"
        r["updated_at"] = now
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    HIST.write_text(buf.getvalue(), encoding="utf-8")
    for wk, old, new, label in changed:
        print(f"{wk}: {old:>6} -> {new:6.1f}  ({label})")
    print(f"{len(changed)} UK ai_layoffs_ytd rows backfilled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
