#!/usr/bin/env python3
"""Offline tests for the v2 real adapters and the backfill pipeline.

No network access required - every HTTP call is served from canned
fixtures. Run:  python3 scripts/test_adapters.py
"""
import csv
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import update_data as ud  # noqa: E402
import backfill_real_history as bf  # noqa: E402

PASS = 0

def ok(label):
    global PASS
    PASS += 1
    print(f"  ok {PASS:2d}  {label}")

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

WEEK_FRIDAYS = ["2026-03-06", "2026-03-13", "2026-03-20", "2026-03-27",
                "2026-04-03", "2026-04-10", "2026-04-17", "2026-04-24",
                "2026-05-01", "2026-05-08", "2026-05-15", "2026-05-22",
                "2026-05-29", "2026-06-05"]

def hl_csv(cc):
    rows = ["date,jobcountry,indeed_job_postings_index,variable,display_name"]
    for i, d in enumerate(WEEK_FRIDAYS):
        for j, sec in enumerate(ud.EXPOSED_SECTORS):
            rows.append(f"{d},{cc},{70 + i * 0.5 + j},total postings,{sec}")
            rows.append(f"{d},{cc},{50 + j},new postings,{sec}")
        rows.append(f"{d},{cc},120,total postings,Nursing")  # non-exposed
    return "\n".join(rows)

BLS_JSON = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {"series": [
        {"seriesID": "LNS14000000", "data": [
            {"year": "2026", "period": "M05", "value": "-"},   # BLS placeholder
            {"year": "2026", "period": "M04", "value": "4.6"},
            {"year": "2026", "period": "M03", "value": "4.5"},
            {"year": "2026", "period": "M02", "value": "4.4"}]},
        {"seriesID": "LNS14000036", "data": [
            {"year": "2026", "period": "M05", "value": "-"},
            {"year": "2026", "period": "M04", "value": "8.1"},
            {"year": "2026", "period": "M03", "value": "7.9"},
            {"year": "2026", "period": "M02", "value": "7.7"}]},
    ]},
}

def ons_json(base):
    return json.dumps({"months": [
        {"date": "2026 FEB", "value": str(base)},
        {"date": "2026 MAR", "value": str(base + 0.1)},
        {"date": "2026 APR", "value": str(base + 0.2)},
    ]})

def eurostat_json(v1, v2):
    return json.dumps({
        "value": {"0": v1, "1": v2},
        "dimension": {"time": {"category": {"index":
            {"2026-03": 0, "2026-04": 1}}}},
    })

def abs_slice_json(age_id, age_name, obs):
    """Single-series ABS SDMX-JSON slice (LF or LF_AGES layout)."""
    return json.dumps({
        "structure": {"dimensions": {
            "series": [
                {"id": "MEASURE", "values": [{"id": "M13", "name": "Unemployment rate"}]},
                {"id": "SEX", "values": [{"id": "3", "name": "Persons"}]},
                {"id": "AGE", "values": [{"id": age_id, "name": age_name}]},
                {"id": "TSEST", "values": [{"id": "20", "name": "Seasonally Adjusted"}]},
                {"id": "REGION", "values": [{"id": "AUS", "name": "Australia"}]},
                {"id": "FREQ", "values": [{"id": "M", "name": "Monthly"}]},
            ],
            "observation": [{"id": "TIME_PERIOD", "values": [
                {"id": "2026-03"}, {"id": "2026-04"}]}],
        }},
        "dataSets": [{"series": {
            "0:0:0:0:0:0": {"observations": {"0": [obs[0]], "1": [obs[1]]}},
        }}],
    })

ONS_BEAO_CSV = "\n".join([
    '"Title","LFS: ILO redundancy level (thousands): UK: All: SA"',
    '"CDID","BEAO"',
    '"2026 FEB","104"',
    '"2026 MAR","106"',
    '"2026 APR","108"',
])

EUROSTAT_GRAD_JSON = json.dumps({
    "value": {"0": 81.3, "1": 81.6},
    "dimension": {"time": {"category": {"index": {"2024": 0, "2025": 1}}}},
})

BLS_EMP_JSON = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {"series": [
        {"seriesID": "LNS12000036", "data":
            [{"year": "2022", "period": f"M{m:02d}", "value": "20000"}
             for m in range(1, 13)]
            + [{"year": "2026", "period": "M06", "value": "19000"}]},
    ]},
}

def adzuna_search_json(count):
    return json.dumps({"count": count, "results": []})

def adzuna_history_json(avg):
    return json.dumps({"month": {"2026-06": avg, "2026-05": avg * 0.99}})

ABS_DSD_XML = """<?xml version="1.0"?>
<mes:Structure xmlns:mes="http://x/message" xmlns:str="http://x/structure" xmlns:com="http://x/common">
 <str:DataStructure id="LF">
  <str:DimensionList>
   <str:Dimension id="MEASURE" position="1"><str:LocalRepresentation><str:Enumeration><com:Ref class="Codelist" id="CL_MEASURE"/></str:Enumeration></str:LocalRepresentation></str:Dimension>
   <str:Dimension id="SEX" position="2"><str:LocalRepresentation><str:Enumeration><com:Ref class="Codelist" id="CL_SEX"/></str:Enumeration></str:LocalRepresentation></str:Dimension>
   <str:Dimension id="AGE" position="3"><str:LocalRepresentation><str:Enumeration><com:Ref class="Codelist" id="CL_AGE"/></str:Enumeration></str:LocalRepresentation></str:Dimension>
   <str:Dimension id="TSEST" position="4"><str:LocalRepresentation><str:Enumeration><com:Ref class="Codelist" id="CL_TSEST"/></str:Enumeration></str:LocalRepresentation></str:Dimension>
   <str:Dimension id="REGION" position="5"><str:LocalRepresentation><str:Enumeration><com:Ref class="Codelist" id="CL_REGION"/></str:Enumeration></str:LocalRepresentation></str:Dimension>
   <str:Dimension id="FREQ" position="6"><str:LocalRepresentation><str:Enumeration><com:Ref class="Codelist" id="CL_FREQ"/></str:Enumeration></str:LocalRepresentation></str:Dimension>
   <str:TimeDimension id="TIME_PERIOD" position="7"/>
  </str:DimensionList>
 </str:DataStructure>
 <str:Codelist id="CL_MEASURE">
  <str:Code id="M12"><com:Name>Employed total</com:Name></str:Code>
  <str:Code id="M13"><com:Name>Unemployment rate</com:Name></str:Code>
 </str:Codelist>
 <str:Codelist id="CL_SEX"><str:Code id="3"><com:Name>Persons</com:Name></str:Code></str:Codelist>
 <str:Codelist id="CL_AGE">
  <str:Code id="1599"><com:Name>All ages</com:Name></str:Code>
  <str:Code id="1524"><com:Name>15-24 years</com:Name></str:Code>
 </str:Codelist>
 <str:Codelist id="CL_TSEST"><str:Code id="20"><com:Name>Seasonally Adjusted</com:Name></str:Code></str:Codelist>
 <str:Codelist id="CL_REGION"><str:Code id="AUS"><com:Name>Australia</com:Name></str:Code></str:Codelist>
 <str:Codelist id="CL_FREQ"><str:Code id="M"><com:Name>Monthly</com:Name></str:Code></str:Codelist>
</mes:Structure>"""

ABS_JSON = {
    "structure": {"dimensions": {
        "series": [
            {"id": "MEASURE", "values": [
                {"id": "M12", "name": "Employed total"},
                {"id": "M13", "name": "Unemployment rate"}]},
            {"id": "SEX", "values": [{"id": "3", "name": "Persons"}]},
            {"id": "AGE", "values": [
                {"id": "1599", "name": "All ages"},
                {"id": "1524", "name": "15-24 years"}]},
            {"id": "TSEST", "values": [
                {"id": "20", "name": "Seasonally Adjusted"}]},
        ],
        "observation": [{"id": "TIME_PERIOD", "values": [
            {"id": "2026-03"}, {"id": "2026-04"}]}],
    }},
    "dataSets": [{"series": {
        "1:0:0:0": {"observations": {"0": [4.0], "1": [4.1]}},
        "1:0:1:0": {"observations": {"0": [9.6], "1": [9.9]}},
        "0:0:0:0": {"observations": {"0": [14500.0], "1": [14550.0]}},
    }}],
}

CHALLENGER_INDEX = ('<a href="https://www.challengergray.com/blog/'
                    'challenger-report-may-job-cuts-rise-16-from-april-highest-may-total-since-2020/">x</a>')
CHALLENGER_POST = ("<p>For the year, AI has been cited in 87,714 cuts, or 22% "
                   "of all 2026 layoffs.</p>")

def build_http_fixtures():
    """Map every URL the adapters hit to a canned body."""
    fixtures = {}
    for cc in sorted({c for codes in ud.HL_COUNTRY.values() for c in codes}):
        fixtures[f"{ud.HL_RAW}/{cc}/job_postings_by_sector_{cc}.csv"] = hl_csv(cc)
    fixtures["https://www.ons.gov.uk/" + ud.ONS_SERIES_PATH["MGSX"] + "/data"] = ons_json(5.0)
    fixtures["https://www.ons.gov.uk/" + ud.ONS_SERIES_PATH["YBVQ"] + "/data"] = ons_json(13.6)
    base = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "une_rt_m?format=JSON&lang=EN&geo=EU27_2020&s_adj=SA&unit=PC_ACT&sex=T"
            "&sinceTimePeriod=2025-01&age=")
    fixtures[base + "TOTAL"] = eurostat_json(5.9, 5.8)
    fixtures[base + "Y_LT25"] = eurostat_json(14.4, 14.6)
    fixtures["https://data.api.abs.gov.au/rest/data/ABS,LF,1.0.0/"
             "M13.3.1599.20.AUS.M?startPeriod=2025-01&format=jsondata"] = \
        abs_slice_json("1599", "Total (age)", (4.0, 4.1))
    fixtures["https://data.api.abs.gov.au/rest/data/ABS,LF_AGES,1.0.0/"
             "M13.3.1524.20.AUS.M?startPeriod=2025-01&format=jsondata"] = \
        abs_slice_json("1524", "15 - 24 years", (9.6, 9.9))
    # UK redundancy proxy (BEAO), EU graduate proxy (edat_lfse_24)
    fixtures["https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/"
             "peoplenotinwork/redundancies/timeseries/beao/lms"] = ONS_BEAO_CSV
    fixtures["https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
             "edat_lfse_24?format=JSON&lang=EN&geo=EU27_2020&sex=T&age=Y20-34"
             "&isced11=ED5-8&duration=Y1-3&unit=PC&lastTimePeriod=2"] = EUROSTAT_GRAD_JSON
    # Adzuna fixtures (IN mention share + premium sample)
    import urllib.parse as _up
    def _adz(cc, path="search/1", **params):
        qs = _up.urlencode({"app_id": "test-id", "app_key": "test-key",
                            "results_per_page": 1, **params})
        return f"{ud.ADZUNA_API}/{cc}/{path}?{qs}"
    for cc in ("in", "sg"):
        fixtures[_adz(cc, what_or=ud.ADZUNA_AI_TERMS)] = adzuna_search_json(4200)
        fixtures[_adz(cc)] = adzuna_search_json(100000)
        for cat in ud.ADZUNA_EXPOSED_CATS:
            fixtures[_adz(cc, category=cat)] = adzuna_search_json(5000)
        fixtures[_adz(cc, path="history", what="artificial intelligence")] = \
            adzuna_history_json(1300000.0)
        fixtures[_adz(cc, path="history")] = adzuna_history_json(1000000.0)
    fixtures[ud.CHALLENGER_BLOG] = CHALLENGER_INDEX
    fixtures["https://www.challengergray.com/blog/challenger-report-may-job-cuts-rise-16-from-april-highest-may-total-since-2020/"] = CHALLENGER_POST
    return fixtures

# ------------------------------------------------------------------
# Parser tests (monkeypatched _http_get/_http_post_json)
# ------------------------------------------------------------------

def run_parser_tests(fixtures):
    ud._CACHE.clear()
    ud._http_get = lambda url, timeout=40: fixtures[url]

    def _bls_dispatch(url, payload, timeout=40):
        if payload.get("seriesid") == ["LNS12000036"]:
            return BLS_EMP_JSON
        return BLS_JSON
    ud._http_post_json = _bls_dispatch

    v, src, _ = ud._adapter_hl("US", "2026-06-07")
    # latest date <= 2026-06-07 is 2026-06-05 (i=13): mean(70+6.5+j for j 0..7)=80
    assert v == 80.0, v
    assert "Hiring Lab" in src
    ok("hiring-lab composite: correct date pick and 8-sector mean")

    v, src, _ = ud._adapter_hl("EU", "2026-03-08")
    assert v == 73.5 and "DE+FR" in src  # mean of DE,FR at 2026-03-06: 70+3.5
    ok("hiring-lab composite: EU = DE+FR mean, early-week date")

    v, src, _ = ud._adapter_unemp("US", "2026-06-07")
    assert v == 3.5 and "BLS" in src  # 8.1 - 4.6 (April latest valid; May is '-')
    ok("BLS delta: skips '-' placeholders, April youth-overall = +3.5pp")

    v, src, _ = ud._adapter_unemp("US", "2026-03-15")
    assert v == 3.4, v  # latest reference month <= March is March: 7.9 - 4.5
    ok("BLS delta: respects week-month cutoff (March for mid-March week)")

    v, src, _ = ud._adapter_unemp("UK", "2026-06-07")
    assert v == 8.6 and "ONS" in src  # (13.6+0.2) - (5.0+0.2)
    ok("ONS delta: YBVQ minus MGSX")

    v, src, _ = ud._adapter_unemp("EU", "2026-06-07")
    assert v == 8.8 and "Eurostat" in src  # 14.6 - 5.8
    ok("Eurostat delta: <25 minus total")

    v, src, _ = ud._adapter_unemp("AU", "2026-06-07")
    assert v == 5.8 and "ABS" in src  # 9.9 - 4.1
    ok("ABS delta: dimension discovery matched M13/15-24/SA")

    v, src, _ = ud._adapter_challenger("US", "2026-06-07")
    assert v == 87.71 and "Challenger" in src
    ok("Challenger: AI-cited YTD parsed to 87.71k")

    # --- new adapters (2026-08 upgrade) ---
    v, src, _ = ud._adapter_ons_redundancy("UK", "2026-06-07")
    assert v == 108.0 and "all-cause" in src
    ok("ONS BEAO: UK redundancy level parsed, all-cause label")

    v, src, _ = ud._adapter_eurostat_graduate("EU", "2026-06-07")
    assert v == 0.3 and "2025 vs 2024" in src, (v, src)
    ok("Eurostat edat_lfse_24: graduate-rate YoY delta = +0.3pp")

    v, src, _ = ud._adapter_bls_youth_emp("US", "2026-06-07")
    assert v == -5.0 and "2022 avg" in src, (v, src)
    ok("BLS youth employment: 19000 vs 20000 avg = -5.0%")

    import os as _os, tempfile as _tf
    _os.environ["ADZUNA_APP_ID"] = "test-id"
    _os.environ["ADZUNA_APP_KEY"] = "test-key"
    old_state = ud.ADZUNA_STATE
    ud.ADZUNA_STATE = Path(_tf.mkdtemp(prefix="adz_")) / "adzuna_state.json"
    try:
        v, src, _ = ud._adapter_adzuna_mention("IN", "2026-06-07")
        assert v == 4.2 and "keyword proxy" in src, (v, src)
        ok("Adzuna mention share: 4200/100000 = 4.2%")

        v, src, _ = ud._adapter_adzuna_posting("IN", "2026-06-07")
        assert v == 100.0 and "=100" in src, (v, src)
        ok("Adzuna posting index: first run anchors baseline at 100")

        v, src, _ = ud._adapter_adzuna_premium("APAC", "2026-06-07")
        assert v == 30.0 and "SG" in src, (v, src)
        ok("Adzuna premium: 1.3M vs 1.0M = +30% (SG proxy market)")
    finally:
        ud.ADZUNA_STATE = old_state
        del _os.environ["ADZUNA_APP_ID"], _os.environ["ADZUNA_APP_KEY"]

    try:
        ud._adapter_adzuna_mention("IN", "2026-06-07")
        raise AssertionError("Adzuna without key should raise")
    except ValueError as exc:
        assert "not set" in str(exc)
    ok("Adzuna adapters raise cleanly when no API key is configured")

    # resolve_value: measured path
    val, s, u, m = ud.resolve_value("US", "topq_unemp_delta", "2026-06-07")
    assert m == "measured" and val == 3.5
    ok("resolve_value: measured flag for wired pair")

    # resolve_value: fallback path on source failure
    def boom(url, timeout=40):
        raise OSError("source down")
    ud._CACHE.clear()
    ud._http_get, ud._http_post_json = boom, lambda *a, **k: boom("x")
    val, s, u, m = ud.resolve_value("US", "topq_unemp_delta", "2026-06-07")
    assert m == "modelled" and isinstance(val, float)
    ok("resolve_value: drift fallback + modelled flag on outage")

    val, s, u, m = ud.resolve_value("IN", "topq_unemp_delta", "2026-06-07")
    assert m == "modelled"
    ok("resolve_value: unwired region stays modelled")

# ------------------------------------------------------------------
# End-to-end backfill dry-run on a copy of the repo data
# ------------------------------------------------------------------

def run_backfill_test(fixtures):
    tmp = Path(tempfile.mkdtemp(prefix="bf_test_"))
    shutil.copytree(ud.DATA, tmp / "data")
    fdir = tmp / "fixtures"
    fdir.mkdir()
    for url, body in fixtures.items():
        (fdir / (hashlib.sha1(url.encode()).hexdigest() + ".txt")).write_text(
            body, encoding="utf-8")
    # BLS is a POST; fixture mode keys POSTs by url|sorted-payload
    bls_payload = {"seriesid": ["LNS14000000", "LNS14000036"],
                   "startyear": "2025", "endyear": str(date.today().year)}
    bls_key = ("https://api.bls.gov/publicAPI/v2/timeseries/data/" + "|"
               + json.dumps(bls_payload, sort_keys=True))
    (fdir / (hashlib.sha1(bls_key.encode()).hexdigest() + ".txt")).write_text(
        json.dumps(BLS_JSON), encoding="utf-8")

    # repoint both modules at the copy, then run backfill in fixture mode
    bf.DATA = tmp / "data"
    bf.SNAP = tmp / "data" / "snapshots"
    bf.CSV_PATH = tmp / "data" / "historical.csv"
    ud._CACHE.clear()
    bf.install_fixture_mode(fdir)
    sys.argv = ["backfill_real_history.py"]
    rc = bf.main()
    assert rc == 0
    ok("backfill: completed on data copy")

    with bf.CSV_PATH.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert all("measurement" in r for r in rows)
    measured = [r for r in rows if r["measurement"] == "measured"]
    pairs = {(r["kpi_id"], r["region_code"]) for r in measured}
    assert ("exposed_posting_index", "US") in pairs
    assert ("exposed_posting_index", "EU") in pairs
    assert ("topq_unemp_delta", "AU") in pairs
    assert ("ai_layoffs_ytd", "US") in pairs
    assert ("ai_layoffs_ytd", "UK") not in pairs   # unwired stays modelled
    assert ("exposed_posting_index", "IN") not in pairs
    ok(f"backfill CSV: {len(measured)} measured rows, wired pairs only")

    # Challenger anchor logic: weeks before 2026-03-31 stay modelled
    early = [r for r in rows if r["kpi_id"] == "ai_layoffs_ytd"
             and r["region_code"] == "US" and r["week_ending"] < "2026-03-31"]
    assert early and all(r["measurement"] == "modelled" for r in early)
    late = [r for r in rows if r["kpi_id"] == "ai_layoffs_ytd"
            and r["region_code"] == "US" and r["week_ending"] >= "2026-05-31"]
    assert late and all(float(r["value"]) == 87.71 for r in late)
    ok("backfill CSV: Challenger anchors applied with pre-anchor weeks modelled")

    cur = json.loads((tmp / "data" / "current.json").read_text(encoding="utf-8"))
    assert cur["regions"]["US"]["kpis"]["topq_unemp_delta"]["measurement"] == "measured"
    assert cur["regions"]["US"]["kpis"]["topq_unemp_delta"]["name"].startswith("Early-career")
    # IN topq is wired via ILOSTAT in the weekly cron (2026-07); the backfill
    # itself can't reproduce its history, so it just preserves whatever badge
    # the source data carries - assert the field is present and valid.
    assert cur["regions"]["IN"]["kpis"]["topq_unemp_delta"]["measurement"] in (
        "measured", "modelled")
    assert "backfilled_at" in cur
    # posting_series rebuilt from measured values for wired regions
    us_series = cur["regions"]["US"]["posting_series"]
    assert len(us_series) == 12 and us_series[-1]["value"] == 80.0
    ok("backfill snapshots: kpi nodes, rename, badges and posting_series rebuilt")

    for p in sorted((tmp / "data" / "snapshots").glob("*.json")):
        json.loads(p.read_text(encoding="utf-8"))
    ok("backfill snapshots: all files still valid JSON")
    shutil.rmtree(tmp)

# ------------------------------------------------------------------

def main():
    print("parser tests")
    fixtures = build_http_fixtures()
    run_parser_tests(fixtures)
    print("backfill dry-run")
    run_backfill_test(fixtures)
    print(f"\nALL {PASS} CHECKS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
