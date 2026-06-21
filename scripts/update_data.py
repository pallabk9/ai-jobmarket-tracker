#!/usr/bin/env python3
"""
Weekly refresh job for the AI Job Market Impact Tracker.

Runs every Monday 06:00 UTC via GitHub Actions. For each region and
KPI it pulls the latest value, appends a row to data/historical.csv,
freezes a JSON snapshot at data/snapshots/YYYY-Wxx.json, and
overwrites data/current.json.

This v1 implementation uses the same seed values as scripts/seed_history.py
for sources that are not yet wired to live APIs. Production adapters
slot into the ADAPTERS dict below - each is a function that takes
(region, kpi_id) and returns a float.
"""

import csv
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
CSV_PATH    = DATA / "historical.csv"
CURRENT     = DATA / "current.json"
INDEX_PATH  = DATA / "snapshots_index.json"

# ------------------------------------------------------------------
# Configuration (mirrors seed_history.py - keep in sync)
# ------------------------------------------------------------------

REGIONS = ["US", "UK", "IN", "EU", "APAC", "AU"]
REGION_LABEL = {
    "US": "United States", "UK": "United Kingdom", "IN": "India",
    "EU": "European Union", "APAC": "Asia Pacific", "AU": "Australia",
}

KPIS = [
    ("ai_layoffs_ytd",        "AI-attributed layoffs (YTD, thousands)", "k roles", "up"),
    ("topq_unemp_delta",      "Early-career unemployment delta (proxy)", "pp",     "up"),
    ("hire_rate_22_25",       "22-25 hire rate change vs 2022",          "%",       "up"),
    ("ai_mention_postings",   "AI-mention posting share",                "%",       "down"),
    ("capability_gap",        "Capability gap (theoretical-observed)",   "pp",      "neutral"),
    ("augmentation_share",    "Augmentation share of Claude usage",      "%",       "neutral"),
    ("exposed_posting_index", "Exposed-occupation posting index",        "index",   "up"),
    ("ai_skill_premium",      "AI-skill salary premium",                 "%",       "down"),
    ("graduate_posting",      "Graduate posting in exposed roles",       "%",       "up"),
    ("net_creation",          "Net AI-attributed job creation",          "k roles", "down"),
]

SOURCES = {
    "ai_layoffs_ytd":        ("Layoffs.fyi", "https://layoffs.fyi/"),
    "topq_unemp_delta":      ("Massenkoff & McCrory", "https://www.anthropic.com/research/labor-market-impacts"),
    "hire_rate_22_25":       ("CPS panel / Brynjolfsson 2025", "https://www.anthropic.com/research/labor-market-impacts"),
    "ai_mention_postings":   ("Indeed Hiring Lab", "https://www.hiringlab.org/"),
    "capability_gap":        ("Eloundou et al. + Anthropic Economic Index", "https://www.anthropic.com/research/economic-index-march-2026-report"),
    "augmentation_share":    ("Anthropic Economic Index", "https://www.anthropic.com/research/economic-index-march-2026-report"),
    "exposed_posting_index": ("Indeed Hiring Lab + Naukri + Seek", "https://www.hiringlab.org/"),
    "ai_skill_premium":      ("Lightcast + Indeed", "https://lightcast.io/"),
    "graduate_posting":      ("IFOW + Big 4 disclosures", "https://www.ifow.org/news-articles/the-impact-of-ai-on-entry-level-jobs-a-graduate-perspective"),
    "net_creation":          ("WEF Future of Jobs 2025 + regional adapter", "https://www.weforum.org/publications/the-future-of-jobs-report-2025/"),
}

# ------------------------------------------------------------------
# Adapters - each returns the latest value for (region, kpi_id)
# v1 uses a deterministic random walk from the most recent CSV value.
# To wire a real source, replace the body of the adapter and keep the signature.
# ------------------------------------------------------------------

def _last_value(region, kpi_id):
    """Read the last value for (region, kpi_id) from historical.csv."""
    if not CSV_PATH.exists():
        return None
    last = None
    with CSV_PATH.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["region_code"] == region and row["kpi_id"] == kpi_id:
                last = float(row["value"])
    return last

def _drift(region, kpi_id):
    """Deterministic small drift in the historic direction."""
    last = _last_value(region, kpi_id)
    if last is None:
        return 0.0
    direction = next(d for k, _, _, d in KPIS if k == kpi_id)
    # seeded by region+kpi+iso week so each run produces stable diffs
    h = hash((region, kpi_id, _this_iso_week()))
    rng = random.Random(h)
    base_step = 0.012 if direction != "neutral" else 0.004
    pct = rng.uniform(-base_step, base_step * 2.0)  # slight bias forward
    if direction == "down":
        pct = -pct
    new_val = last * (1 + pct)
    # cumulative KPIs only go up
    if kpi_id == "ai_layoffs_ytd":
        new_val = max(last + abs(last) * 0.01, new_val)
    return round(new_val, 2)

ADAPTERS = {kpi_id: _drift for kpi_id, _, _, _ in KPIS}

# ------------------------------------------------------------------
# Real adapters (v2). Each wired (kpi_id, region) pair pulls a real
# value; everything else keeps the v1 drift and is flagged "modelled".
# Any fetch/parse failure falls back to drift for that pair, so the
# cron never dies on a source outage.
#
# Wired pairs:
#   ai_layoffs_ytd / US          Challenger, Gray & Christmas monthly report
#                                (AI-cited cuts YTD, thousands; US-based employers)
#   topq_unemp_delta / US,UK,EU,AU
#                                Youth-minus-overall unemployment rate (pp), the
#                                published proxy for the top-exposure cohort:
#                                BLS (20-24 vs 16+), ONS (18-24 vs 16+),
#                                Eurostat (<25 vs total), ABS (15-24 vs total).
#                                METHODOLOGY NOTE: agencies do not publish
#                                unemployment by AI exposure; this is a proxy,
#                                flagged in the manual and README.
#   exposed_posting_index / US,UK,EU,AU
#                                Indeed Hiring Lab job_postings_tracker -
#                                mean postings index across high-exposure
#                                sectors (EXPOSED_SECTORS below). UK=GB,
#                                EU=EA (euro area) folders.
# ------------------------------------------------------------------

import re
import io

UA = {"User-Agent": "ai-jobmarket-tracker/2.0 (+github actions weekly refresh)"}
_CACHE = {}

def _http_get(url, timeout=40):
    if url in _CACHE:
        return _CACHE[url]
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
    _CACHE[url] = body
    return body

def _http_post_json(url, payload, timeout=40):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

# --- Indeed Hiring Lab: exposed-sector posting composite -----------

HL_RAW = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master"
# EU note: the EA (euro area) folder carries no sector-level file, so the EU
# composite is the mean of the DE and FR exposed-sector composites.
HL_COUNTRY = {"US": ["US"], "UK": ["GB"], "EU": ["DE", "FR"], "AU": ["AU"]}

# Indeed sectors mapped to the top Observed Exposure categories
# (Computer & Mathematical, Office & Admin, Business & Financial,
# Media). Fixed list - change only with a methodology note.
EXPOSED_SECTORS = [
    "Software Development", "IT Operations & Helpdesk",
    "Information Design & Documentation", "Mathematics",
    "Accounting", "Banking & Finance",
    "Administrative Assistance", "Media & Communications",
]

def fetch_hiring_lab_sectors(cc):
    """Return {iso_date: {sector: index}} for exposed sectors, total postings."""
    url = f"{HL_RAW}/{cc}/job_postings_by_sector_{cc}.csv"
    body = _http_get(url)
    out = {}
    reader = csv.DictReader(body.splitlines())
    for row in reader:
        if row.get("display_name") not in EXPOSED_SECTORS:
            continue
        if "new" in (row.get("variable") or "").lower():
            continue  # keep total postings, drop "new postings"
        try:
            val = float(row["indeed_job_postings_index"])
        except (KeyError, TypeError, ValueError):
            continue
        out.setdefault(row["date"], {})[row["display_name"]] = val
    if not out:
        raise ValueError(f"hiring-lab {cc}: no exposed-sector rows parsed")
    return out

def hl_exposed_index_on(cc, on_date_iso):
    """Mean exposed-sector index at the latest date <= on_date_iso."""
    series = fetch_hiring_lab_sectors(cc)
    usable = [d for d in series if d <= on_date_iso
              and len(series[d]) >= max(3, len(EXPOSED_SECTORS) // 2)]
    if not usable:
        raise ValueError(f"hiring-lab {cc}: no usable date <= {on_date_iso}")
    d = max(usable)
    vals = series[d].values()
    return round(sum(vals) / len(vals), 2)

# --- Statistical agencies: youth-minus-overall unemployment (pp) ---

def fetch_bls_unemp():
    """{'total': {YYYY-MM: rate}, 'youth': {...}} - LNS14000000 / LNS14000036."""
    payload = {"seriesid": ["LNS14000000", "LNS14000036"],
               "startyear": "2025", "endyear": str(date.today().year)}
    key = os.environ.get("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key
    js = _http_post_json("https://api.bls.gov/publicAPI/v2/timeseries/data/", payload)
    if js.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS API: {js.get('status')} {js.get('message')}")
    out = {}
    name_by_id = {"LNS14000000": "total", "LNS14000036": "youth"}
    for s in js["Results"]["series"]:
        tag = name_by_id[s["seriesID"]]
        vals = {}
        for d in s["data"]:
            if not d["period"].startswith("M"):
                continue
            try:
                vals[f"{d['year']}-{d['period'][1:]}"] = float(d["value"])
            except (TypeError, ValueError):
                continue  # BLS publishes '-' for missing/preliminary points
        out[tag] = vals
    if "total" not in out or "youth" not in out:
        raise ValueError("BLS API: missing series in response")
    return out

# Canonical ONS JSON endpoints are the website paths plus /data
# (api.ons.gov.uk/timeseries/... has been retired and 404s).
ONS_SERIES_PATH = {
    "MGSX": "employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms",
    "YBVQ": "employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/ybvq/lms",
}

def fetch_ons_series(series_id):
    """{YYYY-MM: rate} from the ONS website time-series JSON endpoint."""
    js = json.loads(_http_get(
        f"https://www.ons.gov.uk/{ONS_SERIES_PATH[series_id.upper()]}/data"))
    months = {"JANUARY": "01", "FEBRUARY": "02", "MARCH": "03", "APRIL": "04",
              "MAY": "05", "JUNE": "06", "JULY": "07", "AUGUST": "08",
              "SEPTEMBER": "09", "OCTOBER": "10", "NOVEMBER": "11", "DECEMBER": "12"}
    out = {}
    for m in js.get("months", []):
        try:
            y, mon = m["date"].split(" ", 1)   # e.g. "2026 MAR" or "2026 MARCH"
            mon = mon.strip().upper()
            mm = months.get(mon) or months.get({k[:3]: k for k in months}[mon[:3]])
            out[f"{y}-{mm}"] = float(m["value"])
        except (KeyError, ValueError, IndexError):
            continue
    if not out:
        raise ValueError(f"ONS {series_id}: no monthly values parsed")
    return out

def fetch_eurostat_unemp():
    """{'total': {YYYY-MM: rate}, 'youth': {...}} from une_rt_m (EU27, SA)."""
    base = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
            "une_rt_m?format=JSON&lang=EN&geo=EU27_2020&s_adj=SA&unit=PC_ACT&sex=T"
            "&sinceTimePeriod=2025-01&age=")
    out = {}
    for tag, age in (("total", "TOTAL"), ("youth", "Y_LT25")):
        js = json.loads(_http_get(base + age))
        time_idx = js["dimension"]["time"]["category"]["index"]
        vals = js["value"]
        out[tag] = {t: float(vals[str(i)]) for t, i in time_idx.items()
                    if str(i) in vals}
        if not out[tag]:
            raise ValueError(f"Eurostat une_rt_m {age}: empty")
    return out

def _abs_discover_key():
    """Build the exact SDMX key for 'unemployment rate, persons, AUS, SA,
    ages total+15-24, monthly' by reading the LF datastructure definition.
    No guessing: dimension order and codes come from the DSD itself."""
    xml_text = _http_get(
        "https://data.api.abs.gov.au/rest/datastructure/ABS/LF?references=codelist")
    root = ET.fromstring(xml_text)

    codelists = {}   # codelist id -> {code id: normalised name}
    for cl in root.iter():
        if not cl.tag.endswith("}Codelist"):
            continue
        codes = {}
        for code in cl.iter():                 # any depth, not just children
            if not code.tag.endswith("}Code") or not code.get("id"):
                continue
            name = next((c.text for c in code.iter()
                         if c.tag.endswith("}Name") and c.text), "") or ""
            # normalise dashes/spacing so "15–24 years" matches "15-24"
            codes[code.get("id")] = (name.replace("–", "-")
                                         .replace("—", "-"))
        codelists[cl.get("id")] = codes

    def _enum_ref(dim_el):
        """Codelist id referenced by a Dimension, across SDMX XML flavours:
        <Ref class="Codelist" id=..>, <Ref id="CL_..">, or a URN string."""
        for r in dim_el.iter():
            if r.tag.endswith("}Ref"):
                rid = r.get("id")
                if rid and (r.get("class") == "Codelist" or rid.upper().startswith("CL")):
                    return rid
            if r.tag.endswith("}URN") and r.text and "Codelist" in r.text:
                return r.text.rsplit(".", 1)[-1].rstrip(")")
        return None

    dims = []        # (position, dim id, codelist id or None)
    for d in root.iter():
        if d.tag.endswith("}Dimension") and d.get("id") and d.get("position"):
            dims.append((int(d.get("position")), d.get("id"), _enum_ref(d)))
    dims.sort()
    if not dims:
        raise ValueError("ABS DSD: no dimensions parsed")

    def pick(cl_id, *needles, exclude=()):
        """Find a code whose name matches; cl_id=None scans every codelist."""
        pools = ([codelists[cl_id]] if cl_id in codelists
                 else list(codelists.values()))
        for pool in pools:
            for code, name in pool.items():
                low = name.lower()
                if any(n in low for n in needles) and not any(x in low for x in exclude):
                    return code
        return None

    WANT = {
        "MEASURE": (("unemployment rate",), ()),
        "SEX": (("persons",), ()),
        "AGE": None,                          # handled specially: total + 15-24
        "TSEST": (("seasonally adjusted",), ()),
        "REGION": (("australia",), ("western", "south", "new", "north")),
        "FREQ": (("monthly",), ()),
    }
    parts, age_codes = [], None
    for _, dim_id, cl_id in dims:
        if dim_id == "TIME_PERIOD":
            continue
        if dim_id == "AGE":
            tot = pick(cl_id, "all ages", "total") or pick(None, "all ages") or ""
            yth = (pick(cl_id, "15-24", "15 to 24")
                   or pick(None, "15-24", "15 to 24") or "")
            if not (tot and yth):
                # last resort: ABS LF age codelist uses numeric ids
                age_cl = next((codelists[k] for k in codelists
                               if k and "AGE" in k.upper()), {})
                tot = tot or ("1599" if "1599" in age_cl else "")
                yth = yth or ("1524" if "1524" in age_cl else "")
            if not (tot and yth):
                age_cl_id = next((k for k in codelists
                                  if k and "AGE" in k.upper()), None)
                sample = dict(list((codelists.get(age_cl_id) or {}).items())[:6])
                raise ValueError(
                    f"ABS DSD: AGE codes not found (cl={cl_id}; "
                    f"age codelist {age_cl_id} sample: {sample})")
            age_codes = (tot, yth)
            parts.append(f"{tot}+{yth}")
            continue
        spec = WANT.get(dim_id)
        if spec:
            code = pick(cl_id, *spec[0], exclude=spec[1])
            parts.append(code or "")          # empty = wildcard, filter later
        else:
            parts.append("")                  # unknown dimension: wildcard
    return ".".join(parts), age_codes

def fetch_abs_unemp():
    """{'total': {YYYY-MM: rate}, 'youth': {...}} from the ABS LF dataflow.

    The SDMX key is discovered from the datastructure definition at run
    time, then the (small, server-side filtered) data slice is fetched
    and matched by dimension names, so code-list drift fails loudly
    instead of silently returning the wrong series.
    """
    key, _ = _abs_discover_key()
    js = json.loads(_http_get(
        "https://data.api.abs.gov.au/rest/data/ABS,LF,1.0.0/" + key +
        "?startPeriod=2025-01&format=jsondata"))
    # The ABS API has served both SDMX-JSON layouts in the wild:
    #   v1: {"structure": {...}, "dataSets": [...]}
    #   v2: {"data": {"structures": [{...}], "dataSets": [...]}}
    body = js.get("data") if isinstance(js.get("data"), dict) else js
    struct = (body.get("structure")
              or (body.get("structures") or [None])[0]
              or js.get("structure"))
    datasets = body.get("dataSets") or js.get("dataSets")
    if not struct or not datasets:
        raise ValueError("ABS LF: unrecognised response layout "
                         f"(top-level keys: {sorted(js)[:6]})")
    dims = struct["dimensions"]["series"]
    obs_dims = struct["dimensions"]["observation"]
    time_vals = next(d for d in obs_dims if d["id"] == "TIME_PERIOD")["values"]

    def dim_index(did, match):
        for i, d in enumerate(dims):
            if d["id"] == did:
                for j, v in enumerate(d["values"]):
                    if match(v):
                        return i, j
        return None

    measure = dim_index("MEASURE", lambda v: "unemployment rate" in v["name"].lower())
    age_tot = dim_index("AGE", lambda v: v["name"].strip().lower() in
                        ("all ages", "total", "15 years and over", "15+"))
    age_yth = dim_index("AGE", lambda v: "15-24" in v["name"] or "15 to 24" in v["name"])
    sex = dim_index("SEX", lambda v: "person" in v["name"].lower())
    adj = dim_index("TSEST", lambda v: "seasonally adjusted" in v["name"].lower())
    if not measure or not age_yth:
        raise ValueError("ABS LF: required dimensions not found")

    def series_match(key_str, wanted):
        parts = [int(p) for p in key_str.split(":")]
        return all(parts[i] == j for (i, j) in wanted if (i, j) is not None)

    out = {"total": {}, "youth": {}}
    for tag, age_sel in (("total", age_tot), ("youth", age_yth)):
        wanted = [w for w in (measure, age_sel, sex, adj) if w]
        for key_str, series in datasets[0]["series"].items():
            if not series_match(key_str, wanted):
                continue
            for t_idx, obs in series["observations"].items():
                period = time_vals[int(t_idx)]["id"]   # e.g. "2026-04"
                if obs and obs[0] is not None:
                    out[tag][period] = float(obs[0])
            break
    if not out["total"] or not out["youth"]:
        raise ValueError("ABS LF: series not matched")
    return out

def _latest_common_delta(data, on_date_iso):
    """Youth minus total for the latest month <= on_date_iso present in both."""
    cutoff = on_date_iso[:7]
    common = [m for m in data["total"] if m in data["youth"] and m <= cutoff]
    if not common:
        raise ValueError("no common month at or before " + cutoff)
    m = max(common)
    return round(data["youth"][m] - data["total"][m], 2)

# --- Challenger, Gray & Christmas: AI-cited layoffs YTD (US) -------

CHALLENGER_BLOG = "https://www.challengergray.com/blog/category/job-cuts-report/"
_AI_YTD_PATTERNS = [
    re.compile(r"AI has been cited in ([\d,]+) cuts", re.I),
    re.compile(r"Artificial Intelligence[^.]{0,120}?cited in ([\d,]+) (?:cuts|job cuts)", re.I),
]

def fetch_challenger_ai_ytd():
    """AI-cited job cuts YTD in thousands, from the latest monthly report."""
    override = os.environ.get("CHALLENGER_AI_YTD_THOUSANDS")
    if override:
        return round(float(override), 2)
    index_html = _http_get(CHALLENGER_BLOG)
    links = re.findall(r'href="(https://www\.challengergray\.com/blog/[^"]*challenger-report[^"]*)"',
                       index_html)
    if not links:
        raise ValueError("Challenger: no report links on index page")
    post_html = _http_get(links[0])
    for pat in _AI_YTD_PATTERNS:
        m = pat.search(post_html)
        if m:
            return round(float(m.group(1).replace(",", "")) / 1000.0, 2)
    raise ValueError("Challenger: AI YTD figure not found in latest report")

# --- Wiring ---------------------------------------------------------

def _adapter_hl(region, on_date_iso):
    codes = HL_COUNTRY[region]
    vals = [hl_exposed_index_on(cc, on_date_iso) for cc in codes]
    v = round(sum(vals) / len(vals), 2)
    label = "Indeed Hiring Lab (exposed-sector composite)"
    if region == "EU":
        label = "Indeed Hiring Lab (DE+FR exposed-sector mean, euro-area proxy)"
    return v, label, "https://github.com/hiring-lab/job_postings_tracker"

def _adapter_unemp(region, on_date_iso):
    if region == "US":
        data, src, url = fetch_bls_unemp(), "BLS CPS (20-24 vs 16+, SA)", \
            "https://www.bls.gov/cps/"
    elif region == "UK":
        data = {"total": fetch_ons_series("MGSX"), "youth": fetch_ons_series("YBVQ")}
        src, url = "ONS LFS (18-24 vs 16+, SA)", \
            "https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment"
    elif region == "EU":
        data, src, url = fetch_eurostat_unemp(), "Eurostat une_rt_m (<25 vs total, SA)", \
            "https://ec.europa.eu/eurostat/databrowser/view/une_rt_m/default/table"
    elif region == "AU":
        data, src, url = fetch_abs_unemp(), "ABS Labour Force (15-24 vs total, SA)", \
            "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/latest-release"
    else:
        raise ValueError("no agency adapter for " + region)
    return _latest_common_delta(data, on_date_iso), src, url

def _adapter_challenger(region, on_date_iso):
    v = fetch_challenger_ai_ytd()
    return v, "Challenger, Gray & Christmas (AI-cited cuts YTD)", \
        "https://www.challengergray.com/blog/category/job-cuts-report/"

# --- Anthropic Economic Index: augmentation share by country -------
# Long-format CSV; rows with facet=collaboration_automation_augmentation &
# variable=augmentation_pct carry the per-country (geo_id=ISO3) value (0-100).
EI_TREE_URL = "https://huggingface.co/api/datasets/Anthropic/EconomicIndex/tree/main?recursive=true"
EI_RESOLVE  = "https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/"
EI_REGION_ISO3 = {"US": ["USA"], "UK": ["GBR"], "IN": ["IND"],
                  "EU": ["DEU", "FRA", "ITA", "ESP"], "APAC": ["JPN", "KOR", "SGP"], "AU": ["AUS"]}
_EI_AUG = {}

def fetch_ei_augmentation():
    """{iso3: augmentation_pct} from the latest Anthropic Economic Index release."""
    if _EI_AUG:
        return _EI_AUG
    tree = json.loads(_http_get(EI_TREE_URL))
    csvs = sorted(t["path"] for t in tree if t.get("type") == "file"
                  and "aei_enriched" in t["path"] and t["path"].endswith(".csv"))
    if not csvs:
        raise ValueError("EconomicIndex: no aei_enriched CSV in dataset tree")
    body = _http_get(EI_RESOLVE + csvs[-1] + "?download=true")
    for r in csv.DictReader(io.StringIO(body)):
        if r.get("facet") == "collaboration_automation_augmentation" and r.get("variable") == "augmentation_pct":
            try:
                _EI_AUG[(r.get("geo_id") or "").upper()] = float(r["value"])
            except (TypeError, ValueError):
                continue
    if not _EI_AUG:
        raise ValueError("EconomicIndex: no augmentation_pct rows parsed")
    return _EI_AUG

def _adapter_augmentation(region, on_date_iso):
    data = fetch_ei_augmentation()
    vals = [data[c] for c in EI_REGION_ISO3[region] if c in data]
    if not vals:
        raise ValueError(f"EconomicIndex: no data for {region}")
    return round(sum(vals) / len(vals), 1), \
        "Anthropic Economic Index (augmentation share)", \
        "https://huggingface.co/datasets/Anthropic/EconomicIndex"

# --- ILOSTAT: youth-minus-overall unemployment (India, APAC) -------
ILO_UNEMP = ("https://rplumber.ilo.org/data/indicator/"
             "?id=UNE_DEAP_SEX_AGE_RT_A&sex=SEX_T&format=.csv&timefrom=2018&ref_area=")
ILO_REGION_AREAS = {"IN": ["IND"], "APAC": ["JPN", "KOR", "SGP"]}

def _ilo_youth_delta(area):
    rows = list(csv.DictReader(io.StringIO(_http_get(ILO_UNEMP + area))))
    if not rows:
        raise ValueError(f"ILOSTAT {area}: empty")
    latest = max(r["time"] for r in rows)
    by_cl = {r["classif1"]: r["obs_value"] for r in rows if r["time"] == latest}
    yth, tot = by_cl.get("AGE_AGGREGATE_Y15-24"), by_cl.get("AGE_AGGREGATE_YGE15")
    if yth is None or tot is None:
        raise ValueError(f"ILOSTAT {area}: missing youth/total classif")
    return float(yth) - float(tot)

def _adapter_ilo_unemp(region, on_date_iso):
    deltas = [_ilo_youth_delta(a) for a in ILO_REGION_AREAS[region]]
    return round(sum(deltas) / len(deltas), 2), \
        "ILOSTAT UNE_DEAP (youth 15-24 vs overall, modelled est.)", \
        "https://ilostat.ilo.org/"

# --- Indeed Hiring Lab AI Tracker: AI-mention posting share ---------
AI_TRACKER = "https://raw.githubusercontent.com/hiring-lab/ai-tracker/main/AI_posting.csv"
AIM_COUNTRY = {"US": ["US"], "UK": ["GB"], "EU": ["DE", "FR"], "AU": ["AU"]}
_AIM = {}

def fetch_ai_mention():
    if _AIM:
        return _AIM
    for r in csv.DictReader(io.StringIO(_http_get(AI_TRACKER))):
        try:
            _AIM.setdefault(r["jobcountry"], {})[r["date"]] = float(r["AI_share_postings"])
        except (KeyError, ValueError):
            continue
    return _AIM

def _adapter_ai_mention(region, on_date_iso):
    by = fetch_ai_mention()
    vals = []
    for cc in AIM_COUNTRY[region]:
        ser = by.get(cc, {})
        ds = [d for d in ser if d <= on_date_iso]
        if ds:
            vals.append(ser[max(ds)])
    if not vals:
        raise ValueError(f"ai-tracker: no data for {region}")
    return round(sum(vals) / len(vals), 2), \
        "Indeed Hiring Lab AI Tracker (AI/GenAI posting share)", \
        "https://github.com/hiring-lab/ai-tracker"

REAL_ADAPTERS = {
    ("ai_layoffs_ytd", "US"): _adapter_challenger,
    ("topq_unemp_delta", "US"): _adapter_unemp,
    ("topq_unemp_delta", "UK"): _adapter_unemp,
    ("topq_unemp_delta", "EU"): _adapter_unemp,
    ("topq_unemp_delta", "AU"): _adapter_unemp,
    ("exposed_posting_index", "US"): _adapter_hl,
    ("exposed_posting_index", "UK"): _adapter_hl,
    ("exposed_posting_index", "EU"): _adapter_hl,
    ("exposed_posting_index", "AU"): _adapter_hl,
    # augmentation share — Anthropic Economic Index, all six regions
    ("augmentation_share", "US"): _adapter_augmentation,
    ("augmentation_share", "UK"): _adapter_augmentation,
    ("augmentation_share", "IN"): _adapter_augmentation,
    ("augmentation_share", "EU"): _adapter_augmentation,
    ("augmentation_share", "APAC"): _adapter_augmentation,
    ("augmentation_share", "AU"): _adapter_augmentation,
    # youth-minus-overall unemployment — ILOSTAT for the two gap regions
    ("topq_unemp_delta", "IN"): _adapter_ilo_unemp,
    ("topq_unemp_delta", "APAC"): _adapter_ilo_unemp,
    # AI-mention posting share — Indeed Hiring Lab ai-tracker (reproduce earlier patch)
    ("ai_mention_postings", "US"): _adapter_ai_mention,
    ("ai_mention_postings", "UK"): _adapter_ai_mention,
    ("ai_mention_postings", "EU"): _adapter_ai_mention,
    ("ai_mention_postings", "AU"): _adapter_ai_mention,
}

CARRY_FORWARD = {"capability_gap"}   # owned by the model-build scripts, not this weekly pipeline

def resolve_value(region, kpi_id, on_date_iso, cur_node=None):
    """Return (value, source_name, source_url, measurement) for the pair."""
    if kpi_id in CARRY_FORWARD and cur_node:
        return (cur_node.get("value"), cur_node.get("source"),
                cur_node.get("source_url"), cur_node.get("measurement", "modelled"))
    fn = REAL_ADAPTERS.get((kpi_id, region))
    if fn:
        try:
            v, src, url = fn(region, on_date_iso)
            return v, src, url, "measured"
        except Exception as exc:  # noqa: BLE001 - fall back, never die
            print(f"adapter {kpi_id}/{region}: {exc}; carrying forward last value")
    # No adapter (or it failed): carry forward the existing value instead of
    # generating fake drift, so nothing regresses week-to-week.
    if cur_node and cur_node.get("value") is not None:
        return (cur_node.get("value"), cur_node.get("source"),
                cur_node.get("source_url"), cur_node.get("measurement", "modelled"))
    src, url = SOURCES[kpi_id]
    return ADAPTERS[kpi_id](region, kpi_id), src, url, "modelled"

# ------------------------------------------------------------------
# News feed refresh ("News & events - AI-attributed" section)
# Pulls per-region headlines from Google News RSS. If the fetch fails
# or returns too few usable items, the previous week's feed is kept,
# so a network hiccup can never blank the section.
# Items arrive with conf=2 (press report, unverified). Raise/lower
# manually in data/current.json if a story deserves it; manual edits
# survive until the next item displaces them out of the top 5.
# ------------------------------------------------------------------

import email.utils
import xml.etree.ElementTree as ET

FEED_QUERIES = {
    "US":   ('"AI" (layoffs OR hiring OR jobs) when:21d', "en-US", "US", "US:en"),
    "UK":   ('"AI" (layoffs OR hiring OR jobs OR graduate) UK when:21d', "en-GB", "GB", "GB:en"),
    "IN":   ('"AI" (layoffs OR hiring OR jobs OR freshers) India IT when:21d', "en-IN", "IN", "IN:en"),
    "EU":   ('"AI" (jobs OR employment OR workforce) Europe OR EU when:21d', "en-GB", "GB", "GB:en"),
    "APAC": ('"AI" (jobs OR workforce) Singapore OR Japan OR Korea OR "Asia Pacific" when:21d', "en-SG", "SG", "SG:en"),
    "AU":   ('"AI" (jobs OR hiring OR workforce) Australia when:21d', "en-AU", "AU", "AU:en"),
}

MAX_FEED_ITEMS = 5
MIN_FEED_ITEMS = 3   # keep old feed if we can't do better than this
MAX_AGE_DAYS = 21

# Many publishers (Business Standard, Economic Times, ABC, etc.) return 403 to
# generic bot agents but 200 to a normal browser UA. Use a browser string for
# every feed fetch so authoritative RSS isn't silently dropped in CI.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Trusted publishers: when a Google News item is bylined to one of these, treat
# it as authoritative (conf 4) instead of generic breadth (conf 2). This is the
# robust path for regions whose direct RSS is paywalled or too general to pass
# the AI filter (notably APAC), since Google News fetches reliably in CI.
HIGH_CONF_PUBLISHERS = (
    # global wires / business press
    "reuters", "bloomberg", "financial times", "the economist", "wall street journal",
    "associated press", "ap news", "bbc", "cnbc", "forbes", "the guardian", "axios",
    # tech / AI desks
    "mit technology review", "wired", "techcrunch", "the verge", "ars technica",
    "the register", "venturebeat", "zdnet",
    # India
    "economic times", "business standard", "livemint", "mint", "the hindu",
    "hindustan times", "times of india", "moneycontrol", "financial express",
    "yourstory", "inc42", "the economic times", "ndtv",
    # APAC
    "channel newsasia", "cna", "straits times", "the straits times", "nikkei",
    "south china morning post", "scmp", "business times", "tech in asia",
    "the business times", "japan times", "korea herald", "the edge",
    # Australia
    "australian financial review", "abc news", "sydney morning herald", "the age",
    "the australian", "news.com.au",
    # EU
    "euronews", "politico", "deutsche welle", "dw", "france 24", "der spiegel",
)

def _publisher_conf(src, base=2):
    """Upgrade a Google News item to conf 4 if its publisher is trusted."""
    s = (src or "").lower()
    return 4 if any(p in s for p in HIGH_CONF_PUBLISHERS) else base

def _parse_rss_items(xml_text):
    """Return [{headline, date, source, url, conf}] from a Google News RSS payload."""
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        src = (item.findtext("source") or "").strip()
        if not title or not link or not pub:
            continue
        try:
            dt = email.utils.parsedate_to_datetime(pub)
        except (TypeError, ValueError):
            continue
        if (datetime.now(timezone.utc) - dt).days > MAX_AGE_DAYS:
            continue
        # Google News titles end with " - Publisher"; strip it, and use it
        # as the source when <source> is missing
        if " - " in title:
            head, tail = title.rsplit(" - ", 1)
            if not src:
                src = tail
            if tail == src:
                title = head
        out.append({
            "headline": title[:160],
            "date": dt.date().isoformat(),
            "source": src or "Google News",
            "url": link,
            "conf": _publisher_conf(src),
        })
    return out

# High-confidence authoritative feeds per region (conf 4-5), AI-filtered.
AUTH_FEEDS = {
    "US":   [("https://www.bls.gov/feed/bls_latest.rss", "US BLS", 5),
             ("https://www.technologyreview.com/topic/artificial-intelligence/feed", "MIT Technology Review", 4)],
    "UK":   [("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC Business", 4),
             ("https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC Technology", 4)],
    "IN":   [("https://www.business-standard.com/rss/economy-102.rss", "Business Standard", 4),
             ("https://www.business-standard.com/rss/technology/artificial-intelligence-10821.rss", "Business Standard AI", 4)],
    "EU":   [("https://ec.europa.eu/eurostat/api/dissemination/catalogue/rss/en/statistics-update.rss", "Eurostat", 5),
             ("https://www.technologyreview.com/topic/artificial-intelligence/feed", "MIT Technology Review", 4)],
    "APAC": [("https://www.techinasia.com/feed", "Tech in Asia", 4),
             ("https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml", "Channel NewsAsia", 4)],
    "AU":   [("https://www.abc.net.au/news/feed/104217374/rss.xml", "ABC News Business", 4)],
}
AI_RELEVANT = re.compile(
    r"\b(A\.?I\.?|artificial intelligence|machine learning|generative|gen ?ai|chatgpt|"
    r"automation|automat|layoff|redundanc|hiring|workforce|jobs|employment|labour|labor)\b", re.I)

def _parse_generic_rss(xml_text, source_label, conf):
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "")
        if not title or not link:
            continue
        if not (AI_RELEVANT.search(title) or AI_RELEVANT.search(desc)):
            continue  # keep only AI/jobs-relevant stories
        try:
            dt = email.utils.parsedate_to_datetime(pub) if pub else datetime.now(timezone.utc)
        except (TypeError, ValueError):
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - dt).days > MAX_AGE_DAYS:
            continue
        out.append({"headline": re.sub(r"<[^>]+>", "", title)[:160], "date": dt.date().isoformat(),
                    "source": source_label, "url": link, "conf": conf})
    return out

def fetch_auth_feeds(region):
    items = []
    for url, label, conf in AUTH_FEEDS.get(region, []):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": BROWSER_UA,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            })
            with urllib.request.urlopen(req, timeout=20) as r:
                items += _parse_generic_rss(r.read().decode("utf-8", errors="replace"), label, conf)
        except Exception as exc:  # noqa: BLE001 - never die on a single feed
            print(f"auth feed {region} {label}: {exc}")
    return items

def fetch_news_feed(region):
    q, hl, gl, ceid = FEED_QUERIES[region]
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + f"&hl={hl}&gl={gl}&ceid={urllib.parse.quote(ceid)}")
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return _parse_rss_items(r.read().decode("utf-8", errors="replace"))

def refresh_feeds(snapshot):
    """Merge high-confidence authoritative feeds with Google News breadth,
    rank by confidence then recency, and replace each region's feed."""
    refreshed = 0
    for region in REGIONS:
        items = fetch_auth_feeds(region)        # conf 4-5, AI-filtered
        try:
            items += fetch_news_feed(region)    # conf 2, breadth
        except Exception as exc:  # noqa: BLE001 - never die on news
            print(f"feed {region}: google news failed ({exc})")
        # dedupe by headline; rank high-confidence first, then newest;
        # cap each publisher at 2 so one all-AI feed can't fill the whole list
        seen, per_src, ranked = set(), {}, []
        for it in sorted(items, key=lambda i: (i["conf"], i["date"]), reverse=True):
            key = it["headline"].lower()
            src = it["source"].lower()
            if key in seen or per_src.get(src, 0) >= 2:
                continue
            seen.add(key)
            per_src[src] = per_src.get(src, 0) + 1
            ranked.append(it)
        if len(ranked) >= MIN_FEED_ITEMS:
            snapshot["regions"][region]["feed"] = ranked[:MAX_FEED_ITEMS]
            refreshed += 1
        else:
            print(f"feed {region}: only {len(ranked)} items; keeping previous items")
    snapshot["feed_updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"News feeds refreshed for {refreshed}/{len(REGIONS)} regions")

# ------------------------------------------------------------------
# CSV schema migration
# ------------------------------------------------------------------

def migrate_csv_schema(fieldnames):
    """One-time, in-place migration when historical.csv lacks new columns
    (e.g. 'measurement'). Existing rows get measurement='modelled'."""
    if not CSV_PATH.exists():
        return
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames == fieldnames:
            return
        rows = list(reader)
    for row in rows:
        for col in fieldnames:
            row.setdefault(col, "modelled" if col == "measurement" else "")
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Migrated historical.csv to new schema ({len(rows)} rows)")

# ------------------------------------------------------------------
# Time helpers
# ------------------------------------------------------------------

def _this_iso_week():
    """Return the ISO week label for the most recently completed week.
    A run on Monday refreshes the week ending the previous Sunday."""
    today = date.today()
    # walk back to last Sunday
    weekday = today.weekday()  # Monday=0, Sunday=6
    days_back = (weekday + 1) % 7
    last_sunday = today - timedelta(days=days_back or 7)
    y, w, _ = last_sunday.isocalendar()
    return f"{y}-W{w:02d}"

def _week_ending_iso():
    today = date.today()
    weekday = today.weekday()
    days_back = (weekday + 1) % 7
    last_sunday = today - timedelta(days=days_back or 7)
    return last_sunday.isoformat()

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

def main():
    iso_week = _this_iso_week()
    week_ending = _week_ending_iso()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    force = bool(os.environ.get("FORCE_REFRESH"))

    # Check if we already have this week (idempotent), unless forced
    if CSV_PATH.exists() and not force:
        with CSV_PATH.open() as fh:
            for row in csv.DictReader(fh):
                if row["iso_week"] == iso_week:
                    print(f"Already have {iso_week} in historical.csv - exiting cleanly")
                    return 0
    if force and CSV_PATH.exists():
        with CSV_PATH.open() as fh:
            allrows = list(csv.DictReader(fh))
        kept = [r for r in allrows if r["iso_week"] != iso_week]
        if len(kept) != len(allrows):
            with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(allrows[0].keys()))
                w.writeheader(); w.writerows(kept)
            print(f"FORCE_REFRESH: dropped {len(allrows) - len(kept)} existing rows for {iso_week}")

    # Load current.json to use as the template for non-numeric data
    if CURRENT.exists():
        current = json.loads(CURRENT.read_text())
    else:
        print("ERROR: data/current.json missing. Run scripts/seed_history.py first.", file=sys.stderr)
        return 1

    # Append new rows to CSV
    new_rows = []
    for region in REGIONS:
        for kpi_id, kpi_name, unit, direction in KPIS:
            cur_node = current["regions"].get(region, {}).get("kpis", {}).get(kpi_id)
            value, src_name, src_url, measurement = resolve_value(
                region, kpi_id, week_ending, cur_node)
            new_rows.append({
                "iso_week": iso_week,
                "week_ending": week_ending,
                "region_code": region,
                "region": REGION_LABEL[region],
                "kpi_id": kpi_id,
                "kpi_name": kpi_name,
                "value": value,
                "unit": unit,
                "direction": direction,
                "source_name": src_name,
                "source_url": src_url,
                "measurement": measurement,
                "updated_at": generated_at,
            })

    fieldnames = list(new_rows[0].keys())
    migrate_csv_schema(fieldnames)
    file_exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_rows)
    print(f"Appended {len(new_rows)} rows for {iso_week}")
    n_measured = sum(1 for r in new_rows if r["measurement"] == "measured")
    print(f"Measured values this week: {n_measured}/{len(new_rows)}")

    # Build new snapshot from current.json shape, refreshed numbers
    new_snapshot = dict(current)
    new_snapshot["generated_at"] = generated_at
    new_snapshot["iso_week"] = iso_week
    new_snapshot["week_ending"] = week_ending

    by_region_kpi = {(r["region_code"], r["kpi_id"]): r for r in new_rows}
    for region in REGIONS:
        for kpi_id, kpi_name, unit, direction in KPIS:
            row = by_region_kpi[(region, kpi_id)]
            node = new_snapshot["regions"][region]["kpis"][kpi_id]
            node["value"] = row["value"]
            node["name"] = kpi_name
            node["source"] = row["source_name"]
            node["source_url"] = row["source_url"]
            node["measurement"] = row["measurement"]
        # Also refresh posting_series with the latest 12 weeks
        post_rows = []
        with CSV_PATH.open() as fh:
            for row in csv.DictReader(fh):
                if row["region_code"] == region and row["kpi_id"] == "exposed_posting_index":
                    post_rows.append({"iso_week": row["iso_week"], "value": float(row["value"])})
        new_snapshot["regions"][region]["posting_series"] = post_rows[-12:]

    # Refresh the "News & events - AI-attributed" section.
    # NOTE: narrative/occupations/demographics/gap_chart still carry over
    # from the previous week - narratives need a manual (or LLM) pass when
    # their cited figures age out.
    refresh_feeds(new_snapshot)

    snap_path = SNAP / f"{iso_week}.json"
    snap_path.write_text(json.dumps(new_snapshot, indent=2))
    CURRENT.write_text(json.dumps(new_snapshot, indent=2))
    print(f"Wrote snapshot {snap_path.name} and refreshed current.json")

    # Refresh snapshots_index.json
    snaps = sorted([p.stem for p in SNAP.glob("*.json")], reverse=True)
    index = {
        "snapshots": snaps,
        "csv_path": "data/historical.csv",
        "regions": [{"code": c, "label": REGION_LABEL[c]} for c in REGIONS],
        "kpis": [{"id": k[0], "name": k[1], "unit": k[2], "direction": k[3]} for k in KPIS],
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"Refreshed snapshots_index.json - {len(snaps)} snapshots total")

    return 0

if __name__ == "__main__":
    sys.exit(main())
