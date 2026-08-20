#!/usr/bin/env python3
"""
Weekly sector signals refresh (Phase 1: US, UK, EU, AU).

Fills the `signals` block of each region-sector in data/sectors.json and
appends an archive row per signal to data/sector_series.csv. The exposure
blocks are owned by scripts/build_sector_model.py (quarterly) and are
never touched here.

Signals per sector (each carries measured/modelled provenance):
  postings    Indeed Hiring Lab job_postings_by_sector_{CC}.csv - weekly
              index (Feb 2020 = 100); dashboard sectors map onto Indeed's
              41 occupational sectors via model/sector_concordance.csv.
              US, UK(GB), EU(DE+FR mean), AU.
  employment  US: BLS CES monthly (series in concordance).
              UK: ONS JOBS02 workforce jobs by SIC section (quarterly).
              EU: Eurostat lfsq_egan2 sections + lfsq_egan22d 2-digit
                  splits for banking(K64)/insurance(K65)/IT(J62+J63)/
                  telecom&media(J58-J61) (quarterly).
              AU: ABS Labour Account LABOUR_ACCT_Q by ANZSIC division.
  vacancies   UK: ONS VACS02 by SIC section (monthly).
              EU: Eurostat jvs_q_nace2 job-vacancy RATE (quarterly).
              AU: ABS JV vacancies by ANZSIC division (quarterly).

Failure contract: any fetch/parse error leaves the existing signal node
untouched and logs the reason - the cron never dies on a source outage.
"""

import csv
import io
import json
import os
import sys
from datetime import datetime, timezone, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_data import _http_get, _http_post_json  # noqa: E402
from build_sector_model import _jsonstat_cells       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SECTORS_JSON = ROOT / "data" / "sectors.json"
SERIES_CSV = ROOT / "data" / "sector_series.csv"
CONCORDANCE = ROOT / "model" / "sector_concordance.csv"

HL_RAW = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master"
HL_MARKETS = {"US": ["US"], "UK": ["GB"], "EU": ["DE", "FR"], "AU": ["AU"]}

ONS_TS = ("https://www.ons.gov.uk/employmentandlabourmarket/{path}/"
          "timeseries/{cdid}/lms/data")
# JOBS02 workforce jobs by SIC section (SA, thousands) - verified CDIDs.
# A list means the sector spans several sections; values are summed.
UK_EMPLOYMENT_CDIDS = {
    "banking": "JWS7", "insurance": "JWS7",          # K combined
    "it_software": "JWS6", "telecom_media": "JWS6",  # J combined
    "manufacturing": "JWR7", "healthcare": "JWT5",
    "retail": "JWS3", "professional": "JWS9",
    "power_utilities": ["JWR8", "JWR9"],             # D electricity + E water
    # education (P) / government (O) JOBS02 CDIDs not verified - omitted v1
}
# VACS02 vacancies by SIC section (SA, thousands) - verified CDID map.
UK_VACANCY_CDIDS = {
    "banking": "JP9Q", "insurance": "JP9Q",
    "it_software": "JP9P", "telecom_media": "JP9P",
    "manufacturing": "JP9I", "healthcare": "JP9W",
    "retail": "JP9M", "professional": "JP9S",
    "education": "JP9V", "government": "JP9U",
    "power_utilities": ["JP9J", "JP9K"],             # D electricity + E water
}

# "D+E" marks a sector spanning two sections - components are fetched
# individually and summed (all parts required, else the signal is skipped).
EU_SECTION = {"banking": "K", "insurance": "K", "it_software": "J",
              "telecom_media": "J", "manufacturing": "C", "healthcare": "Q",
              "retail": "G", "professional": "M", "education": "P",
              "government": "O", "power_utilities": "D+E"}

def _secs(section):
    """Expand a possibly-compound section code ('D+E') to its parts."""
    return section.split("+")
# 2-digit NACE refinements where the split is real.
EU_NACE2 = {"banking": ["K64"], "insurance": ["K65"],
            "it_software": ["J62_J63"],
            "telecom_media": ["J58", "J59_J60", "J61"]}

AU_DIVISION = {"banking": "K", "insurance": "K", "it_software": "J",
               "telecom_media": "J", "manufacturing": "C", "healthcare": "Q",
               "retail": "G", "professional": "M", "education": "P",
               "government": "O",
               # ANZSIC division D = Electricity, Gas, Water & Waste (one code)
               "power_utilities": "D"}

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_concordance():
    return list(csv.DictReader(CONCORDANCE.open(encoding="utf-8")))

def set_signal(sectors, sid, name, node):
    sec = sectors.setdefault(sid, {})
    sec.setdefault("signals", {})[name] = node

# ------------------------------------------------------------------
# Indeed Hiring Lab sector postings
# ------------------------------------------------------------------

def fetch_hl_sectors(cc):
    """{display_name: [(date, value), ...]} for total postings."""
    text = _http_get(f"{HL_RAW}/{cc}/job_postings_by_sector_{cc}.csv",
                     timeout=120)
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        if (row.get("variable") or "").strip() != "total postings":
            continue
        try:
            v = float(row["indeed_job_postings_index"])
        except (TypeError, ValueError):
            continue
        out.setdefault(row["display_name"].strip(), []).append(
            (row["date"], v))
    for k in out:
        out[k].sort()
    return out

def postings_signals(regions, concordance):
    mapping = {r["sector_id"]: [s.strip() for s in
                                r["indeed_sectors"].split(";") if s.strip()]
               for r in concordance}
    for region, ccs in HL_MARKETS.items():
        try:
            markets = [fetch_hl_sectors(cc) for cc in ccs]
        except Exception as exc:  # noqa: BLE001
            print(f"postings {region}: {exc}; keeping previous")
            continue
        sectors = regions.setdefault(region, {}).setdefault("sectors", {})
        for sid, names in mapping.items():
            if not names:
                continue
            # weekly-ish series: mean across mapped Indeed sectors and markets
            merged = {}
            for mk in markets:
                for name in names:
                    for d, v in mk.get(name, []):
                        merged.setdefault(d, []).append(v)
            if not merged:
                continue
            series = [(d, sum(vs) / len(vs)) for d, vs in sorted(merged.items())]
            # thin dailies to weekly points (every 7th from the end), keep 12
            pts = series[::-7][::-1][-12:] if len(series) > 12 else series
            latest_d, latest_v = series[-1]
            base_v = pts[0][1] if pts else latest_v
            set_signal(sectors, sid, "postings", {
                "value": round(latest_v, 1), "unit": "index (Feb 2020=100)",
                "period": latest_d,
                "delta12w": round(latest_v - base_v, 1),
                "series": [{"date": d, "value": round(v, 1)} for d, v in pts],
                "source": f"Indeed Hiring Lab sectors ({'+'.join(ccs)}: "
                          f"{', '.join(names[:2])}{'…' if len(names) > 2 else ''})",
                "source_url": "https://github.com/hiring-lab/job_postings_tracker",
                "measurement": "measured", "updated_at": NOW,
            })

# ------------------------------------------------------------------
# ONS (UK): JOBS02 employment + VACS02 vacancies
# ------------------------------------------------------------------

def _ons_latest(cdid, path):
    js = json.loads(_http_get(ONS_TS.format(path=path, cdid=cdid), timeout=45))
    for bucket in ("months", "quarters", "years"):
        pts = js.get(bucket) or []
        if pts:
            last, prev = pts[-1], (pts[-2] if len(pts) > 1 else None)
            return (float(last["value"]), last["date"],
                    float(prev["value"]) if prev else None)
    raise ValueError(f"ONS {cdid}: no data points")

def _ons_latest_sum(cdid_or_list, path):
    """_ons_latest for one CDID or a list (multi-section sector: values
    summed; every component must resolve or the whole lookup raises)."""
    cdids = cdid_or_list if isinstance(cdid_or_list, list) else [cdid_or_list]
    tot_v, tot_prev, period = 0.0, 0.0, None
    have_prev = True
    for c in cdids:
        v, p, prev = _ons_latest(c, path)
        tot_v += v
        period = period or p
        if prev is None:
            have_prev = False
        else:
            tot_prev += prev
    return tot_v, period, (tot_prev if have_prev else None)

def uk_signals(regions):
    sectors = regions.setdefault("UK", {}).setdefault("sectors", {})
    for sid, cdid in UK_EMPLOYMENT_CDIDS.items():
        try:
            v, period, prev = _ons_latest_sum(
                cdid, "peopleinwork/employmentandemployeetypes")
            label = "+".join(cdid) if isinstance(cdid, list) else cdid
            set_signal(sectors, sid, "employment", {
                "value": round(v, 1), "unit": "k jobs", "period": period,
                "delta_prev": round(v - prev, 1) if prev is not None else None,
                "source": f"ONS JOBS02 workforce jobs ({label}, SA)",
                "source_url": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/workforcejobsbyindustryjobs02",
                "measurement": "measured", "updated_at": NOW})
        except Exception as exc:  # noqa: BLE001
            print(f"UK employment {sid}: {exc}; keeping previous")
    for sid, cdid in UK_VACANCY_CDIDS.items():
        try:
            v, period, prev = _ons_latest_sum(
                cdid, "peopleinwork/employmentandemployeetypes")
            label = "+".join(cdid) if isinstance(cdid, list) else cdid
            set_signal(sectors, sid, "vacancies", {
                "value": round(v, 1), "unit": "k vacancies", "period": period,
                "delta_prev": round(v - prev, 1) if prev is not None else None,
                "source": f"ONS VACS02 vacancies ({label}, SA)",
                "source_url": "https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment/datasets/vacanciesbyindustryvacs02",
                "measurement": "measured", "updated_at": NOW})
        except Exception as exc:  # noqa: BLE001
            print(f"UK vacancies {sid}: {exc}; keeping previous")

# ------------------------------------------------------------------
# Eurostat (EU): employment + vacancy rate
# ------------------------------------------------------------------

EUROSTAT_API = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/"
                "1.0/data/")

def _eurostat_latest(dataset, extra, dim="nace_r2", codes=()):
    url = (EUROSTAT_API + dataset + "?format=JSON&lang=EN&geo=EU27_2020"
           "&lastTimePeriod=4" + extra
           + "".join(f"&{dim}={c}" for c in codes))
    js = json.loads(_http_get(url, timeout=60))
    cells = _jsonstat_cells(js, ("time", dim))
    by_time = {}
    for (t, c), v in cells.items():
        by_time.setdefault(t, {})[c] = v
    populated = [t for t, d in sorted(by_time.items()) if d]
    if not populated:
        raise ValueError(f"{dataset}: no populated periods")
    latest = populated[-1]
    prev = populated[-2] if len(populated) > 1 else None
    return by_time[latest], (by_time.get(prev) or {}), latest

def eu_signals(regions):
    sectors = regions.setdefault("EU", {}).setdefault("sectors", {})
    # employment: 2-digit splits where real, else section level
    try:
        codes2 = sorted({c for cs in EU_NACE2.values() for c in cs})
        cur2, prev2, p2 = _eurostat_latest(
            "lfsq_egan22d", "&sex=T&age=Y_GE15&unit=THS_PER", codes=codes2)
    except Exception as exc:  # noqa: BLE001
        cur2, prev2, p2 = {}, {}, None
        print(f"EU egan22d: {exc}")
    try:
        secs = sorted({p for s in EU_SECTION.values() for p in _secs(s)})
        curS, prevS, pS = _eurostat_latest(
            "lfsq_egan2", "&sex=T&age=Y_GE15&unit=THS_PER", codes=secs)
    except Exception as exc:  # noqa: BLE001
        curS, prevS, pS = {}, {}, None
        print(f"EU egan2: {exc}")
    for sid, section in EU_SECTION.items():
        try:
            parts = _secs(section)
            if sid in EU_NACE2 and cur2 and all(c in cur2 for c in EU_NACE2[sid]):
                v = sum(cur2[c] for c in EU_NACE2[sid])
                pv = (sum(prev2.get(c, 0) for c in EU_NACE2[sid])
                      if prev2 else None)
                period, src = p2, f"Eurostat lfsq_egan22d ({'+'.join(EU_NACE2[sid])})"
            elif curS and all(p in curS for p in parts):
                v = sum(curS[p] for p in parts)
                pv = (sum((prevS or {}).get(p, 0) for p in parts)
                      if prevS and all(p in (prevS or {}) for p in parts) else None)
                period, src = pS, f"Eurostat lfsq_egan2 (NACE {section})"
            else:
                continue
            set_signal(sectors, sid, "employment", {
                "value": round(v, 1), "unit": "k persons", "period": period,
                "delta_prev": round(v - pv, 1) if pv else None,
                "source": src + ", EU27",
                "source_url": "https://ec.europa.eu/eurostat/databrowser/view/lfsq_egan2/default/table",
                "measurement": "measured", "updated_at": NOW})
        except Exception as exc:  # noqa: BLE001
            print(f"EU employment {sid}: {exc}; keeping previous")
    # vacancy rate by section
    try:
        curV, prevV, pV = _eurostat_latest(
            "jvs_q_nace2", "&s_adj=NSA&sizeclas=TOTAL&indic_em=JVR",
            codes=sorted({p for s in EU_SECTION.values() for p in _secs(s)}))
        for sid, section in EU_SECTION.items():
            if "+" in section or section not in curV:
                # vacancy RATES can't be summed across sections - compound
                # sectors (D+E) skip the EU vacancy signal
                continue
            v, pv = curV[section], (prevV or {}).get(section)
            set_signal(sectors, sid, "vacancies", {
                "value": round(v, 2), "unit": "% vacancy rate", "period": pV,
                "delta_prev": round(v - pv, 2) if pv is not None else None,
                "source": f"Eurostat jvs_q_nace2 JVR (NACE {section}, EU27)",
                "source_url": "https://ec.europa.eu/eurostat/databrowser/view/jvs_q_nace2/default/table",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"EU vacancies: {exc}; keeping previous")

# ------------------------------------------------------------------
# ABS (AU): Labour Account employment + JV vacancies
# ------------------------------------------------------------------

def _abs_csv(flow, key="all", params="?lastNObservations=2&format=csv"):
    text = _http_get(f"https://data.api.abs.gov.au/rest/data/ABS,{flow}/"
                     f"{key}{params}", timeout=120)
    return list(csv.DictReader(io.StringIO(text)))

def au_signals(regions):
    sectors = regions.setdefault("AU", {}).setdefault("sectors", {})
    # employment: Labour Account, employed persons, by division
    try:
        rows = _abs_csv("LABOUR_ACCT_Q")
        col_ind = next(c for c in rows[0] if "IND" in c.upper()
                       and "INDUSTRY" in c.upper() or c == "LABOURACCT_IND")
        by = {}
        for r in rows:
            ind = r.get(col_ind, "")
            measure = (r.get("MEASURE") or "")
            # measure 1: employed persons ('000) - verify by unit column
            if len(ind) == 1 and ind.isalpha():
                try:
                    v = float(r["OBS_VALUE"])
                except (TypeError, ValueError):
                    continue
                by.setdefault((ind, measure), []).append(
                    (r.get("TIME_PERIOD", ""), v))
        measures = sorted({m for (_, m) in by})
        # pick the measure whose magnitudes look like employed persons '000s
        pick = None
        for m in measures:
            sample = [v for (i, mm), pts in by.items() if mm == m
                      for _, v in pts if i == "Q"]
            if sample and 100 < max(sample) < 5000:
                pick = m
                break
        if pick is None and measures:
            pick = measures[0]
        for sid, div in AU_DIVISION.items():
            pts = sorted(by.get((div, pick), []))
            if not pts:
                continue
            (pp, pv), (cp, cv) = (pts[-2] if len(pts) > 1 else pts[-1]), pts[-1]
            set_signal(sectors, sid, "employment", {
                "value": round(cv, 1), "unit": "k persons", "period": cp,
                "delta_prev": round(cv - pv, 1) if len(pts) > 1 else None,
                "source": f"ABS Labour Account (ANZSIC {div}, measure {pick})",
                "source_url": "https://www.abs.gov.au/statistics/labour/labour-accounts",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"AU employment: {exc}; keeping previous")
    # vacancies: JV by division
    try:
        rows = _abs_csv("JV")
        by = {}
        for r in rows:
            ind = r.get("INDUSTRY", "")
            if (r.get("MEASURE") not in ("1", "M1") or len(ind) != 1
                    or not ind.isalpha() or r.get("REGION") not in ("AUS", "0")):
                continue
            try:
                v = float(r["OBS_VALUE"])
            except (TypeError, ValueError):
                continue
            by.setdefault(ind, []).append((r.get("TIME_PERIOD", ""), v))
        if not by:  # sector filter may differ; retry without REGION filter
            for r in rows:
                ind = r.get("INDUSTRY", "")
                if len(ind) == 1 and ind.isalpha():
                    try:
                        by.setdefault(ind, []).append(
                            (r.get("TIME_PERIOD", ""), float(r["OBS_VALUE"])))
                    except (TypeError, ValueError):
                        continue
        for sid, div in AU_DIVISION.items():
            pts = sorted(set(by.get(div, [])))
            if not pts:
                continue
            cp, cv = pts[-1]
            pv = pts[-2][1] if len(pts) > 1 else None
            set_signal(sectors, sid, "vacancies", {
                "value": round(cv, 1), "unit": "k vacancies", "period": cp,
                "delta_prev": round(cv - pv, 1) if pv is not None else None,
                "source": f"ABS Job Vacancies (ANZSIC {div})",
                "source_url": "https://www.abs.gov.au/statistics/labour/jobs/job-vacancies-australia",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"AU vacancies: {exc}; keeping previous")

# ------------------------------------------------------------------
# Phase 2: India + APAC (SG proxy / pooled composites)
# ------------------------------------------------------------------

APAC_AREAS = ["SGP", "JPN", "KOR"]
SECTION = EU_SECTION            # same section->sector spine everywhere

def ilo_employment_signals(regions):
    """Quarterly employment by ISIC section from ILOSTAT for IN (IND) and
    APAC (SGP+JPN+KOR pooled per-area-latest). Quarters can differ across
    the pooled areas - the period label says exactly what was summed."""
    for code, areas in (("IN", ["IND"]), ("APAC", APAC_AREAS)):
        try:
            key = "+".join(areas)
            text = _http_get("https://sdmx.ilo.org/rest/data/"
                             f"ILO,DF_EMP_TEMP_SEX_ECO_NB,1.0/{key}.Q..SEX_T."
                             "?lastNObservations=2&format=csv", timeout=120)
            # per area: {period: {section: value}}
            per_area = {}
            for row in csv.DictReader(io.StringIO(text)):
                eco = row.get("ECO", "")
                if not eco.startswith("ECO_ISIC4_") or len(eco) != len("ECO_ISIC4_A"):
                    continue
                try:
                    v = float(row["OBS_VALUE"])
                except (TypeError, ValueError):
                    continue
                a = row.get("REF_AREA", "?")
                per_area.setdefault(a, {}).setdefault(
                    row.get("TIME_PERIOD", "?"), {})[eco[-1]] = v
            # areas whose quarterly series carry only aggregates fall back
            # to the annual series (same flow, FREQ=A)
            missing = [a for a in areas if a not in per_area]
            if missing:
                text_a = _http_get("https://sdmx.ilo.org/rest/data/"
                                   "ILO,DF_EMP_TEMP_SEX_ECO_NB,1.0/"
                                   f"{'+'.join(missing)}.A..SEX_T."
                                   "?lastNObservations=2&format=csv", timeout=120)
                for row in csv.DictReader(io.StringIO(text_a)):
                    eco = row.get("ECO", "")
                    if not eco.startswith("ECO_ISIC4_") or len(eco) != len("ECO_ISIC4_A"):
                        continue
                    try:
                        v = float(row["OBS_VALUE"])
                    except (TypeError, ValueError):
                        continue
                    a = row.get("REF_AREA", "?")
                    per_area.setdefault(a, {}).setdefault(
                        row.get("TIME_PERIOD", "?"), {})[eco[-1]] = v
            if not per_area:
                raise ValueError("no section rows")
            # per area latest + previous period
            latest_sum, prev_sum, labels = {}, {}, []
            for a, by_p in per_area.items():
                ps = sorted(by_p)
                labels.append(f"{a} {ps[-1]}")
                for sec, v in by_p[ps[-1]].items():
                    latest_sum[sec] = latest_sum.get(sec, 0.0) + v
                if len(ps) > 1:
                    for sec, v in by_p[ps[-2]].items():
                        prev_sum[sec] = prev_sum.get(sec, 0.0) + v
            sectors = regions.setdefault(code, {}).setdefault("sectors", {})
            for sid, sec in SECTION.items():
                parts = _secs(sec)
                if not all(p in latest_sum for p in parts):
                    continue
                v = sum(latest_sum[p] for p in parts)
                pv = (sum(prev_sum.get(p, 0) for p in parts)
                      if all(p in prev_sum for p in parts) else None)
                set_signal(sectors, sid, "employment", {
                    "value": round(v, 1), "unit": "k persons",
                    "period": ", ".join(sorted(labels)),
                    "delta_prev": round(v - pv, 1) if pv else None,
                    "source": f"ILOSTAT EMP_TEMP_SEX_ECO (ISIC {sec}, "
                              + ("pooled " + "+".join(areas) if len(areas) > 1
                                 else areas[0]) + ")",
                    "source_url": "https://ilostat.ilo.org/",
                    "measurement": "measured", "updated_at": NOW})
        except Exception as exc:  # noqa: BLE001
            print(f"{code} ILO employment: {exc}; keeping previous")

SG_VACANCY_DATASET = "d_d3f02543c4d0dd197c56637eefc32624"
SG_INDUSTRY_MAP = {
    "financial services": "banking",
    "insurance services": "insurance",
    "it and other information services": "it_software",
    "telecommunications, broadcasting and publishing": "telecom_media",
    "health and social services": "healthcare",
    "manufacturing": "manufacturing",
    "retail trade": "retail",
    "professional services": "professional",
    "public administration and education": "government",  # SSIC combines the two
}

def sg_vacancy_signals(regions):
    """APAC vacancies proxy: Singapore MOM job vacancies by industry
    (data.gov.sg, quarterly). Sums across occupation groups per industry;
    newest two quarters give level + delta."""
    try:
        base = ("https://data.gov.sg/api/action/datastore_search"
                f"?resource_id={SG_VACANCY_DATASET}")
        total = json.loads(_http_get(base + "&limit=1", timeout=60))["result"]["total"]
        # rows are appended chronologically; the tail holds the newest quarters
        js = json.loads(_http_get(
            base + f"&limit=2000&offset={max(0, int(total) - 2000)}", timeout=90))
        recs = js["result"]["records"]
        if not recs:
            raise ValueError("no records")
        quarters = sorted({r["quarter"] for r in recs}, reverse=True)[:2]
        sums = {q: {} for q in quarters}
        for r in recs:
            q, ind = r.get("quarter"), (r.get("industry") or "").strip().lower()
            sid = SG_INDUSTRY_MAP.get(ind)
            if q not in sums or not sid:
                continue
            try:
                v = float(r.get("job_vacancy"))
            except (TypeError, ValueError):
                continue
            sums[q][sid] = sums[q].get(sid, 0.0) + v
        latest, prev = quarters[0], (quarters[1] if len(quarters) > 1 else None)
        if not sums[latest]:
            raise ValueError(f"no mapped industries in {latest}")
        sectors = regions.setdefault("APAC", {}).setdefault("sectors", {})
        for sid, v in sums[latest].items():
            pv = sums.get(prev, {}).get(sid) if prev else None
            note = " incl. education (SSIC grouping)" if sid == "government" else ""
            set_signal(sectors, sid, "vacancies", {
                "value": round(v), "unit": "vacancies (SG)", "period": latest,
                "delta_prev": round(v - pv) if pv is not None else None,
                "source": f"Singapore MOM job vacancies by industry (SG proxy market{note})",
                "source_url": "https://data.gov.sg/",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"APAC SG vacancies: {exc}; keeping previous")

NAUKRI_RSS = "https://www.naukri.com/blog/tag/naukri-jobspeak/rss/"
NAUKRI_SECTORS = [
    (r"insurance", "insurance"),
    (r"bfsi|banking", "banking"),
    (r"\bit\b|information technology", "it_software"),
    (r"telecom", "telecom_media"),
    (r"manufacturing", "manufacturing"),
    (r"retail", "retail"),
    (r"healthcare|pharma", "healthcare"),
    (r"education", "education"),
    (r"oil\s*&?\s*gas|energy|power|utilit", "power_utilities"),
]

def naukri_signals(regions):
    """India hiring momentum by sector, parsed from the Naukri JobSpeak
    monthly post (Ghost RSS, full HTML in content:encoded). Text-regex on
    published copy - deliberately conservative: needs >=2 sector matches
    or the whole parse is discarded."""
    import re as _re
    try:
        import urllib.request as _ur
        from update_data import BROWSER_UA
        req = _ur.Request(NAUKRI_RSS, headers={
            "User-Agent": BROWSER_UA,
            "Accept": "application/rss+xml, application/xml, */*"})
        with _ur.urlopen(req, timeout=90) as r:
            xml_text = r.read().decode("utf-8", errors="replace")
        m = _re.search(r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>",
                       xml_text, _re.S)
        title_m = _re.search(r"<item>.*?<title>(.*?)</title>", xml_text, _re.S)
        if not m:
            raise ValueError("no content:encoded in RSS")
        html = _re.sub(r"<[^>]+>", " ", m.group(1))
        period = (title_m.group(1).strip() if title_m else "latest report")
        found = {}
        for pat, sid in NAUKRI_SECTORS:
            for sm in _re.finditer(pat, html, _re.I):
                window = html[sm.start():sm.start() + 90]
                pm = _re.search(r"(\d{1,3})\s*%", window)
                if not pm:
                    continue
                val = float(pm.group(1))
                # sign words only count BETWEEN the sector name and its figure -
                # the following sentence may describe a different sector
                lead = window[:pm.end()]
                if _re.search(r"down|declin|fell|drop|negative|-\s*\d", lead, _re.I):
                    val = -val
                if abs(val) <= 60:            # sanity: YoY hiring % band
                    found.setdefault(sid, val)
                break
        if len(found) < 2:
            raise ValueError(f"only {len(found)} sector figures parsed")
        sectors = regions.setdefault("IN", {}).setdefault("sectors", {})
        for sid, val in found.items():
            set_signal(sectors, sid, "momentum", {
                "value": val, "unit": "% YoY hiring", "period": period[:60],
                "delta_prev": None,
                "source": "Naukri JobSpeak monthly (text-parsed from published report)",
                "source_url": "https://www.naukri.com/blog/tag/naukri-jobspeak/",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"IN Naukri momentum: {exc}; keeping previous")

ADZUNA_SECTOR_CATS = {
    "banking": ["accounting-finance-jobs"],
    "it_software": ["it-jobs"],
    "manufacturing": ["manufacturing-jobs"],
    "healthcare": ["healthcare-nursing-jobs"],
    "retail": ["retail-jobs"],
    "professional": ["consultancy-jobs", "legal-jobs", "hr-jobs"],
    "education": ["teaching-jobs"],
    "power_utilities": ["energy-oil-gas-jobs"],
}

def _last_archived(region, sid, signal):
    """Previous archived value from sector_series.csv, for run-over-run deltas."""
    if not SERIES_CSV.exists():
        return None
    last = None
    with SERIES_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row["region"] == region and row["sector_id"] == sid
                    and row["signal"] == signal):
                try:
                    last = float(row["value"])
                except (TypeError, ValueError):
                    continue
    return last

def adzuna_sector_postings(regions):
    """Live posting counts per sector category for IN and APAC (SG), via
    Adzuna. Key-gated: silently skipped until ADZUNA_APP_ID/KEY exist."""
    if not (os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY")):
        return
    from update_data import _adzuna_count, ADZUNA_CC
    for code in ("IN", "APAC"):
        sectors = regions.setdefault(code, {}).setdefault("sectors", {})
        for sid, cats in ADZUNA_SECTOR_CATS.items():
            try:
                total = 0.0
                for cc in ADZUNA_CC[code]:
                    for cat in cats:
                        total += _adzuna_count(cc, category=cat)
                prev = _last_archived(code, sid, "postings")
                market = "+".join(c.upper() for c in ADZUNA_CC[code])
                set_signal(sectors, sid, "postings", {
                    "value": round(total), "unit": "live postings",
                    "period": NOW[:10],
                    "delta_prev": round(total - prev) if prev is not None else None,
                    "series": [],
                    "source": f"Adzuna ({market} categories: {', '.join(cats)})",
                    "source_url": "https://developer.adzuna.com/",
                    "measurement": "measured", "updated_at": NOW})
            except Exception as exc:  # noqa: BLE001
                print(f"{code} Adzuna postings {sid}: {exc}; keeping previous")

# ------------------------------------------------------------------
# Layoffs layer: US Challenger industry table + EU Eurofound ERM
# ------------------------------------------------------------------

# Challenger industry -> dashboard sector. All-cause job cuts; the AI-cited
# share exists only at the total level (tracked by the ai_layoffs_ytd KPI).
CHALLENGER_SECTOR = {
    "Financial": "banking", "FinTech": "banking",
    "Insurance": "insurance",
    "Technology": "it_software",
    "Telecommunications": "telecom_media", "Media": "telecom_media",
    "Aerospace/Defense": "manufacturing", "Apparel": "manufacturing",
    "Automotive": "manufacturing", "Chemical": "manufacturing",
    "Consumer Products": "manufacturing", "Electronics": "manufacturing",
    "Industrial Goods": "manufacturing",
    "Health Care/Products": "healthcare", "Pharmaceutical": "healthcare",
    "Retail": "retail",
    "Services": "professional", "Legal": "professional",
    "Education": "education",
    "Government": "government",
    "Energy": "power_utilities", "Utility": "power_utilities",
}

def parse_challenger_industry_table(text):
    """{sector_id: {'ytd': cuts, 'ytd_prev': cuts}} from the pdftotext
    -layout dump of the monthly report. Industry rows carry up to five
    numbers; the last is YTD current year, second-to-last YTD prior year.
    Rows with fewer than two numbers (sparse industries) are skipped."""
    import re as _re
    out = {}
    in_table = False
    for line in text.splitlines():
        s = line.strip()
        if _re.match(r"Industry\s+\w{3}-\d{2}", s):
            in_table = True
            continue
        if in_table and s.startswith("TOTAL"):
            break
        if not in_table or not s:
            continue
        nums = [n.replace(",", "") for n in _re.findall(r"[\d,]+", s)]
        label = _re.split(r"\s{2,}", s)[0].strip()
        sid = CHALLENGER_SECTOR.get(label)
        if not sid or len(nums) < 2:
            continue
        try:
            ytd, ytd_prev = float(nums[-1]), float(nums[-2])
        except ValueError:
            continue
        node = out.setdefault(sid, {"ytd": 0.0, "ytd_prev": 0.0})
        node["ytd"] += ytd
        node["ytd_prev"] += ytd_prev
    if len(out) < 6:
        raise ValueError(f"Challenger table: only {sorted(out)} parsed")
    return out

def us_layoffs_signals(regions):
    """US per-sector job cuts YTD from the Challenger monthly report PDF.
    Needs pdftotext (poppler-utils) - the weekly workflow installs it;
    absence degrades to carry-forward like any other outage."""
    import re as _re
    import subprocess
    import tempfile
    try:
        from update_data import CHALLENGER_BLOG
        idx = _http_get(CHALLENGER_BLOG, timeout=45)
        posts = _re.findall(
            r'href="(https://www\.challengergray\.com/blog/[^"]*challenger-report[^"]*)"', idx)
        if not posts:
            raise ValueError("no report post on index")
        post = _http_get(posts[0], timeout=45)
        pdfs = _re.findall(r'href="([^"]+\.pdf[^"]*)"', post)
        if not pdfs:
            raise ValueError("no PDF link in report post")
        import urllib.request
        from update_data import UA
        req = urllib.request.Request(pdfs[0], headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(raw)
            pdf_path = fh.name
        txt = subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                             capture_output=True, text=True, timeout=120)
        if txt.returncode != 0:
            raise ValueError(f"pdftotext rc={txt.returncode}")
        table = parse_challenger_industry_table(txt.stdout)
        period = _re.search(r"Challenger-Report-([A-Za-z]+-\d{4})", pdfs[0])
        period = period.group(1).replace("-", " ") if period else "latest report"
        sectors = regions.setdefault("US", {}).setdefault("sectors", {})
        for sid, v in table.items():
            set_signal(sectors, sid, "layoffs", {
                "value": round(v["ytd"]), "unit": "cuts YTD",
                "period": period,
                "delta_prev": round(v["ytd"] - v["ytd_prev"]),
                "delta_label": "vs same YTD last year",
                "source": "Challenger, Gray & Christmas job cuts by industry "
                          "(all-cause; AI-cited share tracked at the headline KPI)",
                "source_url": "https://www.challengergray.com/blog/category/job-cuts-report/",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"US layoffs: {exc}; keeping previous")

# ERM sector -> dashboard sector. The Financial bucket includes insurance
# and real estate (one ERM grouping) - assigned to banking, labelled.
ERM_SECTOR = {
    "Manufacturing": "manufacturing",
    "Wholesale / Retail": "retail",
    "Information / Computing": "it_software",
    "Financial / Insurance/ Estate": "banking",
    "Health / Social work": "healthcare",
    "Professional Services": "professional",
    "Public Administration / Defence": "government",
    "Media": "telecom_media",
    "Education": "education",
    "Electricity": "power_utilities",
    "Water / Waste": "power_utilities",
}
EU27 = {"Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
        "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
        "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
        "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
        "Slovenia", "Spain", "Sweden"}

def eu_layoffs_signals(regions):
    """EU announced job losses per sector, trailing 12 months, from the
    Eurofound European Restructuring Monitor events export."""
    try:
        text = _http_get("https://apps.eurofound.europa.eu/"
                         "restructuring-events/factsheetscsv", timeout=120)
        rows = list(csv.DictReader(io.StringIO(text)))
        if len(rows) < 1000:
            raise ValueError(f"ERM export suspiciously small ({len(rows)})")
        cutoff = (datetime.now(timezone.utc)
                  .replace(day=1)).strftime("%Y-%m")
        year, month = int(cutoff[:4]) - 1, cutoff[5:7]
        start = f"{year}-{month}"
        losses, events = {}, {}
        for r in rows:
            d = (r.get("Announcement date") or "")
            if d[:7] < start or r.get("Country") not in EU27:
                continue
            sid = ERM_SECTOR.get((r.get("Sector") or "").strip())
            if not sid:
                continue
            try:
                change = float((r.get("Employment Change") or "")
                               .replace("+", "").replace(",", ""))
            except ValueError:
                continue
            if change >= 0:
                continue                      # only announced job losses
            losses[sid] = losses.get(sid, 0.0) + (-change)
            events[sid] = events.get(sid, 0) + 1
        if len(losses) < 4:
            raise ValueError(f"only {sorted(losses)} sectors matched")
        sectors = regions.setdefault("EU", {}).setdefault("sectors", {})
        for sid, v in losses.items():
            note = (" - ERM's Financial bucket includes insurance & real estate"
                    if sid == "banking" else "")
            set_signal(sectors, sid, "layoffs", {
                "value": round(v), "unit": "announced job losses (12mo)",
                "period": f"{start} onward",
                "delta_prev": None,
                "events": events[sid],
                "source": f"Eurofound European Restructuring Monitor, EU27, "
                          f"{events[sid]} announcements{note}",
                "source_url": "https://apps.eurofound.europa.eu/restructuringevents/",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"EU layoffs: {exc}; keeping previous")

# ------------------------------------------------------------------
# BLS CES (US): monthly employment by sector
# ------------------------------------------------------------------

def us_signals(regions, concordance):
    sectors = regions.setdefault("US", {}).setdefault("sectors", {})
    series_map = {r["sector_id"]: r["ces_series"].strip()
                  for r in concordance if r["ces_series"].strip()}
    ids = sorted(set(series_map.values()))
    try:
        payload = {"seriesid": ids, "latest": "false",
                   "startyear": str(date.today().year - 1),
                   "endyear": str(date.today().year)}
        key = os.environ.get("BLS_API_KEY")
        if key:
            payload["registrationkey"] = key
        js = _http_post_json(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/", payload,
            timeout=60)
        if js.get("status") != "REQUEST_SUCCEEDED":
            raise ValueError(f"{js.get('status')} {js.get('message')}")
        latest = {}
        for s in js["Results"]["series"]:
            data = [d for d in s.get("data", []) if d["period"].startswith("M")]
            if not data:
                continue
            cur = data[0]
            prev = data[1] if len(data) > 1 else None
            latest[s["seriesID"]] = (
                float(cur["value"].replace(",", "")),
                f"{cur['year']}-{cur['period'][1:]}",
                float(prev["value"].replace(",", "")) if prev else None)
        for sid, series_id in series_map.items():
            if series_id not in latest:
                continue
            v, period, pv = latest[series_id]
            set_signal(sectors, sid, "employment", {
                "value": v, "unit": "k jobs", "period": period,
                "delta_prev": round(v - pv, 1) if pv is not None else None,
                "source": f"BLS CES ({series_id}, SA)",
                "source_url": "https://www.bls.gov/ces/",
                "measurement": "measured", "updated_at": NOW})
    except Exception as exc:  # noqa: BLE001
        print(f"US CES: {exc}; keeping previous")

# ------------------------------------------------------------------

def append_series_archive(regions):
    fieldnames = ["run_date", "region", "sector_id", "signal", "value",
                  "unit", "period", "source", "measurement"]
    exists = SERIES_CSV.exists()
    with SERIES_CSV.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        run = NOW[:10]
        for region, rnode in regions.items():
            for sid, snode in (rnode.get("sectors") or {}).items():
                for name, sig in (snode.get("signals") or {}).items():
                    if sig.get("updated_at") != NOW:
                        continue      # only archive rows refreshed this run
                    w.writerow({"run_date": run, "region": region,
                                "sector_id": sid, "signal": name,
                                "value": sig.get("value"),
                                "unit": sig.get("unit"),
                                "period": sig.get("period"),
                                "source": sig.get("source"),
                                "measurement": sig.get("measurement")})

def main():
    if not SECTORS_JSON.exists():
        print("data/sectors.json missing - run build_sector_model.py first",
              file=sys.stderr)
        return 1
    doc = json.loads(SECTORS_JSON.read_text(encoding="utf-8"))
    regions = doc.setdefault("regions", {})
    concordance = load_concordance()

    postings_signals(regions, concordance)
    uk_signals(regions)
    eu_signals(regions)
    au_signals(regions)
    us_signals(regions, concordance)
    # Phase 2: India + APAC
    ilo_employment_signals(regions)
    sg_vacancy_signals(regions)
    naukri_signals(regions)
    adzuna_sector_postings(regions)
    # Phase 3: layoffs layer (US Challenger industries, EU ERM events)
    us_layoffs_signals(regions)
    eu_layoffs_signals(regions)

    doc["generated_at"] = NOW
    SECTORS_JSON.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    append_series_archive(regions)
    n = sum(1 for r in regions.values() for s in (r.get("sectors") or {}).values()
            for sig in (s.get("signals") or {}).values()
            if sig.get("updated_at") == NOW)
    print(f"sectors.json refreshed - {n} signals updated this run")
    return 0

if __name__ == "__main__":
    sys.exit(main())
