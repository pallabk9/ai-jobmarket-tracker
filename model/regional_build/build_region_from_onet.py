#!/usr/bin/env python3
"""
O*NET-via-ISCO task-time builder for non-US regions (EU, IN, AU, APAC).

All three data sources are fetched at run time and are reachable from CI
(GitHub Actions); only this sandbox is firewalled. No data is committed.

  O*NET Work Activities (importance)      -> per-SOC 18-task profiles
  eworx soc10_isco08 crosswalk (.dta)     -> SOC -> ISCO-08, on GitHub (raw)
  ILOSTAT EMP_TEMP_SEX_OCU_NB             -> employment by ISCO-08 1-digit

Occupation task content is treated as universal across countries (the O*NET
profiles), so per-occupation exposure is the same everywhere; what differs by
region is the WORKFORCE MIX (ILOSTAT employment by ISCO major group). The
headline capability_gap is therefore employment-weighted and differs by region.

Granularity: ISCO-08 1-digit major groups (10). ILOSTAT reports employment by
occupation at 1-digit for most countries; 2-digit coverage is patchy, so 1-digit
keeps every region consistent.

Region -> ILOSTAT ref_area(s) (aggregates summed):
  EU = DEU FRA ITA ESP NLD POL    IN = IND    AU = AUS    APAC = JPN KOR SGP

Usage:  python3 build_region_from_onet.py EU      (needs: pip install pandas)
Overrides: ONET_WA_FILE, SOC_ISCO_DTA_URL, committed isco/<R>_employment.csv.
"""
import csv, io, json, os, sys, datetime, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISCO = HERE / "isco"
SITE = HERE.parent.parent
DATA = SITE / "data"
CACHE = ISCO / "cache"; CACHE.mkdir(parents=True, exist_ok=True)
TASKS = [f"T{i:02d}" for i in range(1, 19)]
WEEK_HOURS = 40.0; WORKING_WEEKS = 48.0
UA = {"User-Agent": "ai-jobmarket-tracker/1.0 (research; pallabk9 github)"}

ONET_VER = os.environ.get("ONET_VER", "db_30_3")
WA_URL = os.environ.get("ONET_WA_URL",
    f"https://www.onetcenter.org/dl_files/database/{ONET_VER}_text/Work%20Activities.txt")
WA_FILE = os.environ.get("ONET_WA_FILE")
DTA_URL = os.environ.get("SOC_ISCO_DTA_URL",
    "https://raw.githubusercontent.com/eworx-org/iscoCrosswalks/master/"
    "data-raw/stata_dset/onetsoc_to_isco_cws_ibs/soc10_isco08.dta")
ILO_BASE = "https://rplumber.ilo.org/data/indicator/?id=EMP_TEMP_SEX_OCU_NB_A&sex=SEX_T&format=.csv&timefrom=2020&ref_area="
REGION_AREAS = {"EU": ["DEU", "FRA", "ITA", "ESP", "NLD", "POL"],
                "IN": ["IND"], "AU": ["AUS"], "APAC": ["JPN", "KOR", "SGP"]}

def _digits(s):
    return "".join(ch for ch in str(s) if ch.isdigit())

def http_get(url, cache_name, binary=False):
    cp = CACHE / cache_name
    if cp.exists():
        return cp.read_bytes() if binary else cp.read_text(encoding="utf-8", errors="replace")
    print(f"  GET {url[:90]}")
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
    cp.write_bytes(data)
    return data if binary else data.decode("utf-8", errors="replace")

def load_scores():
    s, label = {}, {}
    for r in csv.DictReader((HERE / "task_scores.csv").open()):
        s[r["task_id"]] = float(r["ai_susceptibility_may2026"]); label[r["task_id"]] = r["task_category"]
    return s, label

def onet_profiles():
    cx = {}
    for r in csv.DictReader((HERE / "us" / "gwa_task_crosswalk.csv").open()):
        cx.setdefault(r["element_id"], []).append((r["task_id"], float(r["weight"])))
    text = Path(WA_FILE).read_text(encoding="utf-8", errors="replace") if WA_FILE else http_get(WA_URL, "work_activities.txt")
    imp = {}
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        if r.get("Scale ID") != "IM":
            continue
        try:
            imp.setdefault(r["O*NET-SOC Code"], {})[r["Element ID"]] = float(r["Data Value"])
        except (TypeError, ValueError):
            continue
    out = {}
    for soc, ims in imp.items():
        tw = {t: 0.0 for t in TASKS}
        for eid, im in ims.items():
            for task, w in cx.get(eid, []):
                tw[task] += (max(0.0, im - 1.0) ** 2) * w
        tot = sum(tw.values())
        if tot > 0:
            out[_digits(soc.split(".")[0])] = {t: tw[t] / tot * 100.0 for t in TASKS}  # keyed by 6-digit SOC digits
    if not out:
        raise SystemExit("No O*NET profiles parsed")
    return out

def soc_to_isco1():
    """{soc6_digits: set(isco1)} from the eworx soc10->isco08 crosswalk (.dta)."""
    import pandas as pd
    raw = http_get(DTA_URL, "soc10_isco08.dta", binary=True)
    df = pd.read_stata(io.BytesIO(raw))
    cols = {c.lower(): c for c in df.columns}
    sc, ic = cols.get("soc10"), cols.get("isco08")
    if not sc or not ic:
        raise SystemExit(f"crosswalk columns unexpected: {list(df.columns)}")
    m = {}
    for _, row in df.iterrows():
        soc = _digits(row[sc]); isco = _digits(row[ic])
        if len(soc) >= 6 and isco:
            m.setdefault(soc[:6], set()).add(isco.zfill(4)[0])  # ISCO 1-digit major
    if not m:
        raise SystemExit("crosswalk parsed empty")
    return m

def region_employment(region):
    """{isco1: persons} from ILOSTAT (summed over the region's countries)."""
    override = ISCO / f"{region}_employment.csv"
    if override.exists() and override.stat().st_size > 200:
        out = {}
        for r in csv.DictReader(override.open()):
            try:
                out[str(r["isco2_code"]).strip()[:1]] = out.get(str(r["isco2_code"]).strip()[:1], 0.0) + float(str(r["employment"]).replace(",", ""))
            except (KeyError, ValueError):
                continue
        if out:
            return out
    agg = {}
    for area in REGION_AREAS[region]:
        text = http_get(ILO_BASE + area, f"ilo_{area}.csv")
        rows = list(csv.DictReader(io.StringIO(text)))
        latest = max((r["time"] for r in rows), default=None)
        for r in rows:
            if r.get("time") != latest:
                continue
            cl = r.get("classif1", "")
            if cl.startswith("OCU_ISCO08_") and cl.split("_")[-1].isdigit() and len(cl.split("_")[-1]) == 1:
                try:
                    agg[cl.split("_")[-1]] = agg.get(cl.split("_")[-1], 0.0) + float(r["obs_value"]) * 1000.0
                except (TypeError, ValueError):
                    continue
    return agg

def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: build_region_from_onet.py <EU|IN|AU|APAC>")
    region = sys.argv[1].upper()
    sus, label = load_scores()
    groups_meta = {r["group_code"]: (r["group_name"], float(r["adoption_discount"]), float(r["amplification_multiplier"]))
                   for r in csv.DictReader((ISCO / "isco_major_groups.csv").open())}

    profiles = onet_profiles()
    cw = soc_to_isco1()
    print(f"  {len(profiles)} O*NET profiles, {len(cw)} SOC->ISCO rows")
    emp = region_employment(region)
    if not emp:
        raise SystemExit(f"{region}: no ILOSTAT employment - skipping (regions need a workforce mix to differ)")
    print(f"  {len(emp)} ISCO-1 employment groups for {region}")

    # aggregate O*NET profiles to ISCO 1-digit (simple mean of matched SOCs)
    acc = {}
    for soc6, prof in profiles.items():
        for isco1 in cw.get(soc6, ()):
            a = acc.setdefault(isco1, {t: 0.0 for t in TASKS} | {"_n": 0})
            for t in TASKS:
                a[t] += prof[t]
            a["_n"] += 1

    occ = []
    for isco1 in sorted(set(acc) | set(emp)):
        if isco1 not in acc or isco1 not in emp:
            continue
        a = acc[isco1]; n = a["_n"] or 1
        prof = {t: a[t] / n for t in TASKS}
        gname, disc, mult = groups_meta.get(isco1, (f"ISCO {isco1}", 0.5, 1.0))
        alloc = {t: round(prof[t]) for t in TASKS}
        d = 100 - sum(alloc.values())
        if d:
            alloc[max(TASKS, key=lambda t: alloc[t])] += d
        raw = sum(prof[t] * sus[t] for t in TASKS) / 100.0
        pi = raw * disc; hrs = pi * WEEK_HOURS
        occ.append({"soc": isco1, "title": gname, "smg_code": isco1, "smg": gname,
                    "employment": round(emp[isco1]), "discount": round(disc, 3),
                    "raw": round(raw, 4), "pi": round(pi, 4), "hrs_week": round(hrs, 1),
                    "annual_hrs": round(hrs * WORKING_WEEKS), "fte": round(hrs * emp[isco1] / WEEK_HOURS),
                    "mult": mult, "combined_hrs": round(hrs * mult, 2), "tasks": alloc})
    if not occ:
        raise SystemExit("no ISCO majors matched employment+crosswalk")

    glist = [{"code": o["smg_code"], "name": o["smg"], "count": 1, "employment_000": round(o["employment"] / 1000),
              "raw": o["raw"], "practical": o["pi"], "hrs": o["hrs_week"]} for o in occ]
    tot_emp = sum(o["employment"] for o in occ) or 1
    mr = sum(o["raw"] * o["employment"] for o in occ) / tot_emp          # employment-weighted
    mp = sum(o["pi"] * o["employment"] for o in occ) / tot_emp
    gap_pp = round((mr - mp) * 100, 2)

    out = {"region": region, "as_of": f"May 2026 frontier (O*NET {ONET_VER} via ISCO-08 1-digit)",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "AWA AI Impact model (O*NET task profiles -> ISCO-08; ILOSTAT employment mix)",
           "task_labels": label, "total_employment": round(sum(o["employment"] for o in occ)),
           "n_occupations": len(occ), "groups": glist, "occupations": occ}
    (DATA / f"{region.lower()}_occupations.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"Wrote {region.lower()}_occupations.json: {len(occ)} ISCO majors, emp-weighted gap {gap_pp}pp")

    gap_chart = {"cats": [o["smg_code"] for o in occ], "names": [o["smg"] for o in occ],
                 "theoretical": [round(o["raw"] * 100, 1) for o in occ],
                 "observed": [round(o["pi"] * 100, 1) for o in occ],
                 "source": out["source"], "detail": f"{region.lower()}_occupations.json"}
    p = DATA / "current.json"
    if p.exists():
        d = json.loads(p.read_text())
        if region in d["regions"]:
            d["regions"][region]["gap_chart"] = gap_chart
            k = d["regions"][region]["kpis"]["capability_gap"]
            k["value"] = gap_pp; k["source"] = out["source"]
            k["source_url"] = "https://ilostat.ilo.org/"; k["measurement"] = "modelled"
            p.write_text(json.dumps(d, indent=2))
            print(f"Patched current.json: {region} capability_gap={gap_pp}pp")

if __name__ == "__main__":
    main()
