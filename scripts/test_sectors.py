#!/usr/bin/env python3
"""Offline tests for the sector layer (Phase 1). No network needed.
Run:  python3 scripts/test_sectors.py
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_sector_model as bsm   # noqa: E402
import update_sectors as us        # noqa: E402

PASS = 0

def ok(label):
    global PASS
    PASS += 1
    print(f"  ok {PASS:2d}  {label}")

# ---- concordance ----
rows = bsm.load_concordance()
assert len(rows) == 10, len(rows)
ids = [r["sector_id"] for r in rows]
assert ids[0] == "banking" and "insurance" in ids and "it_software" in ids
it = next(r for r in rows if r["sector_id"] == "it_software")
assert "IT Infrastructure, Operations & Support" in it["indeed_sectors"], \
    "quoted comma in indeed_sectors must survive CSV parsing"
ok("concordance: 10 sectors, quoted Indeed names parse correctly")

# ---- SAES math ----
matrix = {"15": 100.0, "43": 100.0}          # even split
expo = {"15": 0.20, "43": 0.10}
score, top = bsm.saes(matrix, expo)
assert score == 15.0, score                   # mean(0.2, 0.1) x100
assert top[0]["key"] == "15" and top[0]["share"] == 0.5
score2, _ = bsm.saes({"15": 300.0, "43": 100.0}, expo)
assert score2 == 17.5, score2                 # 0.75x0.2 + 0.25x0.1
assert bsm.saes({}, expo) == (None, [])
assert bsm.saes({"99": 50.0}, expo) == (None, [])   # unknown occupations drop
ok("SAES: employment-share weighting, empty and unknown-key handling")

# ---- SOC->ISCO exposure means ----
by_major = {"11": 0.10, "15": 0.30, "13": 0.20, "43": 0.05}
isco_vals = {}
for soc, isco in bsm.SOC_TO_ISCO.items():
    if soc in by_major:
        isco_vals.setdefault(isco, []).append(by_major[soc])
assert isco_vals["1"] == [0.10] and isco_vals["3"] == [0.20]
ok("SOC->ISCO map: majors route as documented (13 stands in for ISCO 3)")

# ---- JSON-stat decoding (the Eurostat layout that broke v1) ----
js = {
    "id": ["freq", "nace_r2", "isco08", "time"],
    "size": [1, 1, 3, 2],
    "dimension": {
        "freq": {"category": {"index": {"Q": 0}}},
        "nace_r2": {"category": {"index": {"K": 0}}},
        "isco08": {"category": {"index": {"OC1": 0, "OC2": 1, "OC3": 2}}},
        "time": {"category": {"index": {"2025-Q1": 0, "2025-Q2": 1}}},
    },
    # values only for 2025-Q1 (index*2 + 0): OC1=10, OC2=20; OC3 missing
    "value": {"0": 10.0, "2": 20.0},
}
cells = bsm._jsonstat_cells(js, ("time", "isco08"))
assert cells[("2025-Q1", "OC1")] == 10.0
assert cells[("2025-Q1", "OC2")] == 20.0
assert ("2025-Q2", "OC1") not in cells
ok("JSON-stat: flat-index decode with sparse periods")

# ---- ONS latest-point extraction ----
class _FakeResp:
    pass
def fake_get(url, timeout=45):
    return json.dumps({"months": [
        {"date": "2026 APR", "value": "31"},
        {"date": "2026 MAY", "value": "32"}]})
orig = us._http_get
us._http_get = fake_get
try:
    v, period, prev = us._ons_latest("JP9Q", "peopleinwork/employmentandemployeetypes")
    assert (v, period, prev) == (32.0, "2026 MAY", 31.0)
finally:
    us._http_get = orig
ok("ONS: latest + previous point extraction from timeseries JSON")

# ---- Indeed postings signal shaping ----
def fake_hl(url, timeout=120):
    lines = ["date,jobcountry,indeed_job_postings_index,variable,display_name"]
    for i in range(100):
        d = f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        lines.append(f"{d},GB,{100 + i * 0.1:.1f},total postings,Banking & Finance")
        lines.append(f"{d},GB,{50 + i:.1f},new postings,Banking & Finance")
    return "\n".join(lines)
orig = us._http_get
us._http_get = fake_hl
try:
    regions = {}
    us.postings_signals(regions, rows)
    b = regions["UK"]["sectors"]["banking"]["signals"]["postings"]
    assert b["measurement"] == "measured"
    assert len(b["series"]) <= 12 and b["series"][-1]["value"] == b["value"]
    assert "new postings" not in json.dumps(b)      # filtered out
    ins = regions["UK"]["sectors"].get("insurance", {})
    assert "signals" not in ins or "postings" not in ins.get("signals", {}), \
        "insurance has no Indeed sector and must not get a postings signal"
finally:
    us._http_get = orig
ok("Indeed postings: weekly thinning, total-postings filter, no phantom insurance")

# ---- failure contract: signals survive a source outage ----
def boom(url, timeout=120):
    raise OSError("source down")
orig = us._http_get
us._http_get = boom
try:
    regions = {"UK": {"sectors": {"banking": {"signals": {"postings": {
        "value": 84.8, "measurement": "measured",
        "updated_at": "old"}}}}}}
    us.postings_signals(regions, rows)
    us.uk_signals(regions)
    kept = regions["UK"]["sectors"]["banking"]["signals"]["postings"]
    assert kept["value"] == 84.8 and kept["updated_at"] == "old"
finally:
    us._http_get = orig
ok("failure contract: outage leaves existing signals untouched")

# ---- repo data sanity (uses committed sectors.json) ----
doc = json.loads((HERE.parent / "data" / "sectors.json").read_text())
assert len(doc["taxonomy"]) == 10
for reg in ("UK", "EU", "AU"):
    secs = doc["regions"][reg]["sectors"]
    rels = [s["exposure_rel"] for s in secs.values() if s.get("exposure_rel")]
    assert rels and max(rels) == 100.0, f"{reg}: top sector must index at 100"
    ranks = sorted(s["exposure_rank"] for s in secs.values() if s.get("exposure_rank"))
    assert ranks == list(range(1, len(ranks) + 1)), f"{reg}: ranks not contiguous"
ok("sectors.json: taxonomy, relative index tops at 100, contiguous ranks")

print(f"\nALL {PASS} SECTOR CHECKS PASSED")
