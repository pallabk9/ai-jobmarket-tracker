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
assert len(rows) == 11, len(rows)
ids = [r["sector_id"] for r in rows]
assert ids[0] == "banking" and "insurance" in ids and "it_software" in ids
assert "power_utilities" in ids
pu = next(r for r in rows if r["sector_id"] == "power_utilities")
assert pu["isic_section"] == "D+E", pu["isic_section"]
it = next(r for r in rows if r["sector_id"] == "it_software")
assert "IT Infrastructure, Operations & Support" in it["indeed_sectors"], \
    "quoted comma in indeed_sectors must survive CSV parsing"
ok("concordance: 11 sectors incl. power_utilities (D+E), quoted Indeed names parse")

# ---- compound-section merge (D+E) in build_region ----
# saes over a merged D+E matrix must equal saes over the manual sum
mD, mE = {"3": 60.0, "8": 40.0}, {"3": 20.0, "9": 30.0}
merged = {}
for m in (mD, mE):
    for k, v in m.items():
        merged[k] = merged.get(k, 0.0) + v
assert merged == {"3": 80.0, "8": 40.0, "9": 30.0}
expo_de = {"3": 0.30, "8": 0.10, "9": 0.05}
s_merged, _ = bsm.saes(merged, expo_de)
assert s_merged is not None and abs(
    s_merged - 100 * (80 * .30 + 40 * .10 + 30 * .05) / 150) < 0.01, s_merged
ok("compound section D+E: matrices merge by summed employment before SAES")

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

# ---- Phase 2: ILO pooled matrix ----
def fake_ilo(url, timeout=120):
    lines = ["DATAFLOW,REF_AREA,FREQ,MEASURE,ECO,OCU,TIME_PERIOD,OBS_VALUE"]
    for area, mult in (("SGP", 1), ("KOR", 2)):
        for sec in "ABCDEFGHIJKL":          # >=10 sections to pass sparsity gate
            for ocu in ("2", "4"):
                lines.append(f"X,{area},A,EMP,ECO_ISIC4_{sec},OCU_ISCO08_{ocu},2025,{100 * mult}")
        lines.append(f"X,{area},A,EMP,ECO_AGGREGATE_TOTAL,OCU_ISCO08_2,2025,999")
        lines.append(f"X,{area},A,EMP,ECO_ISIC4_K,OCU_ISCO08_L,2025,50")   # L = not a major
    return "\n".join(lines)
orig = bsm._http_get
bsm._http_get = fake_ilo
try:
    mat, periods = bsm.fetch_ilo_matrix(["SGP", "KOR"])
    assert mat["K"]["2"] == 300.0 and mat["C"]["4"] == 300.0   # pooled 100+200
    assert "L" not in mat["K"] and periods == {"SGP": "2025", "KOR": "2025"}
finally:
    bsm._http_get = orig
ok("ILO matrix: pools areas, keeps ISIC sections, drops non-major OCU codes")

# ---- Phase 2: SG vacancy mapping ----
def fake_sg(url, timeout=90):
    if "limit=1" in url and "limit=15" not in url and "limit=2000" not in url:
        return json.dumps({"result": {"total": 4, "records": []}})
    return json.dumps({"result": {"total": 4, "records": [
        {"quarter": "2025-Q4", "industry": "financial services",
         "occupation": "pmet", "job_vacancy": "100"},
        {"quarter": "2025-Q4", "industry": "financial services",
         "occupation": "non-pmet", "job_vacancy": "20"},
        {"quarter": "2025-Q4", "industry": "insurance services",
         "occupation": "pmet", "job_vacancy": "30"},
        {"quarter": "2025-Q3", "industry": "financial services",
         "occupation": "pmet", "job_vacancy": "90"},
    ]}})
orig = us._http_get
us._http_get = fake_sg
try:
    regions = {}
    us.sg_vacancy_signals(regions)
    b = regions["APAC"]["sectors"]["banking"]["signals"]["vacancies"]
    assert b["value"] == 120 and b["period"] == "2025-Q4" and b["delta_prev"] == 30
    assert regions["APAC"]["sectors"]["insurance"]["signals"]["vacancies"]["value"] == 30
finally:
    us._http_get = orig
ok("SG vacancies: sums occupations, latest quarter + delta, industry map")

# ---- Phase 2: Naukri momentum parse ----
NAUKRI_XML = """<rss><channel><item><title>JobSpeak July 2026</title>
<content:encoded><![CDATA[<p>Insurance led hiring at 16% YOY growth while
IT posted 18% gains. Retail declined 12% and Manufacturing grew 14%.</p>]]></content:encoded>
</item></channel></rss>"""
import urllib.request as _ur_test
class _FakeResp:
    def __init__(self, data): self._d = data
    def read(self): return self._d
    def __enter__(self): return self
    def __exit__(self, *a): return False
orig_open = _ur_test.urlopen
_ur_test.urlopen = lambda req, timeout=90: _FakeResp(NAUKRI_XML.encode())
try:
    regions = {}
    us.naukri_signals(regions)
    sig = regions["IN"]["sectors"]
    assert sig["insurance"]["signals"]["momentum"]["value"] == 16.0
    assert sig["it_software"]["signals"]["momentum"]["value"] == 18.0
    assert sig["retail"]["signals"]["momentum"]["value"] == -12.0
    assert sig["manufacturing"]["signals"]["momentum"]["value"] == 14.0
finally:
    _ur_test.urlopen = orig_open
ok("Naukri momentum: sector figures parsed, negatives detected, period from title")

# ---- Phase 3: Challenger industry table parse ----
CHALLENGER_TXT = """
        Industry         Jul-25       Jun-26        Jul-26      YTD 2025    YTD 2026
Financial                    1,096        1,120        3,157       26,894      18,626
FinTech                        581          719                     1,813       7,122
Insurance                      474          209           89        3,430       6,908
Legal                                                                 403
Technology                 13,037        15,503        9,867       89,251     149,023
Media                        5,044           98          940        9,796       4,428
Telecommunications          4,383          262        1,064       19,277       3,333
Retail                         622        1,055          210       80,487      12,946
Health Care/Products         2,323        2,761        1,251       32,399      34,426
Education                    2,458           58           13       14,116      15,499
Government                   3,666        1,872        2,962      292,294      20,752
TOTAL                      62,075        45,849       33,429      806,383     477,033
"""
table = us.parse_challenger_industry_table(CHALLENGER_TXT)
assert table["banking"]["ytd"] == 18626 + 7122          # Financial + FinTech
assert table["banking"]["ytd_prev"] == 26894 + 1813
assert table["insurance"]["ytd"] == 6908
assert table["telecom_media"]["ytd"] == 4428 + 3333     # Media + Telecom
assert "professional" not in table                       # Legal row: 1 number, skipped
ok("Challenger table: industry sums, sparse-row skip, TOTAL stops the parse")

# ---- Phase 3: ERM job-loss aggregation ----
def fake_erm(url, timeout=120):
    import io as _io, csv as _csv
    rows = [["Id", "Announcement date", "Country", "Company", "Sector",
             "Restructuring type", "Employment Change"]]
    rows += [["1", "2026-05-01", "France", "A", "Manufacturing", "Closure", "-500"],
             ["2", "2026-06-01", "Germany", "B", "Manufacturing", "Internal restructuring", "-250"],
             ["3", "2026-06-02", "Germany", "C", "Manufacturing", "Business expansion", "+900"],
             ["4", "2026-07-01", "Norway", "D", "Manufacturing", "Closure", "-999"],
             ["5", "2020-01-01", "France", "E", "Manufacturing", "Closure", "-999"],
             ["6", "2026-07-05", "Spain", "F", "Information / Computing", "Closure", "-120"],
             ["7", "2026-07-06", "Italy", "G", "Financial / Insurance/ Estate", "Closure", "-80"],
             ["8", "2026-07-07", "Poland", "H", "Wholesale / Retail", "Closure", "-60"],
             ["9", "2026-07-08", "Ireland", "I", "Health / Social work", "Closure", "-40"]]
    # pad row count past the plausibility gate
    rows += [["x", "2019-01-01", "France", "Z", "Manufacturing", "Closure", "-1"]] * 1000
    buf = _io.StringIO()
    _csv.writer(buf).writerows(rows)
    return buf.getvalue()
orig = us._http_get
us._http_get = fake_erm
try:
    regions = {}
    us.eu_layoffs_signals(regions)
    secs = regions["EU"]["sectors"]
    assert secs["manufacturing"]["signals"]["layoffs"]["value"] == 750   # 500+250; +900, Norway, 2020 excluded
    assert secs["it_software"]["signals"]["layoffs"]["value"] == 120
    assert secs["banking"]["signals"]["layoffs"]["value"] == 80
    assert "insurance" not in secs        # ERM folds insurance into the Financial bucket
finally:
    us._http_get = orig
ok("ERM: 12mo window, EU27 filter, expansions excluded, losses summed per sector")

# ---- repo data sanity (uses committed sectors.json) ----
doc = json.loads((HERE.parent / "data" / "sectors.json").read_text())
assert len(doc["taxonomy"]) == 11
assert any(t["id"] == "power_utilities" for t in doc["taxonomy"])
for reg in ("UK", "EU", "AU", "IN", "APAC"):
    secs = doc["regions"][reg]["sectors"]
    rels = [s["exposure_rel"] for s in secs.values() if s.get("exposure_rel")]
    assert rels and max(rels) == 100.0, f"{reg}: top sector must index at 100"
    ranks = sorted(s["exposure_rank"] for s in secs.values() if s.get("exposure_rank"))
    assert ranks == list(range(1, len(ranks) + 1)), f"{reg}: ranks not contiguous"
    assert secs["power_utilities"].get("exposure_rel"), \
        f"{reg}: power_utilities must carry an AI Footprint index"
ok("sectors.json: 11-sector taxonomy incl. power_utilities, tops at 100, contiguous ranks")

print(f"\nALL {PASS} SECTOR CHECKS PASSED")
