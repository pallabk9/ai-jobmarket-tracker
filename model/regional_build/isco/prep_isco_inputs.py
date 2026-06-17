#!/usr/bin/env python3
"""
One-off prep: populate the two committed inputs the regional builder needs:
  isco/soc_isco_crosswalk.csv        SOC6 -> ISCO-08 2-digit
  isco/<REGION>_employment.csv       employment by ISCO-08 2-digit (EU/IN/AU/APAC)

WHY THIS EXISTS: the source hosts (BLS crosswalk, ILOSTAT) block cloud/CI IPs
and the sandbox this was built in. Run it from a normal machine (your laptop)
or any non-cloud network, commit the two outputs, then run the
build-regions-model workflow (which only needs O*NET, reachable from CI).

    pip install pandas openpyxl xlrd requests
    python3 prep_isco_inputs.py

Sources, all confirmed to exist (see model/regional_build/isco/README.md):
  crosswalk : BLS "ISCO-08 x SOC" crosswalk  https://www.bls.gov/soc/ISCO_SOC_Crosswalk.xls
  employment: ILOSTAT EMP_TEMP_SEX_OCU_NB_A (employment by sex & occupation,
              ISCO-08 2-digit) via the rplumber CSV endpoint.
Region -> ILOSTAT ref_area (aggregates summed; edit to taste):
  EU = DEU+FRA   IN = IND   AU = AUS   APAC = SGP+JPN+KOR
"""
import csv, io, sys
from pathlib import Path
import requests
import pandas as pd

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "ai-jobmarket-tracker/1.0 (research)"}
REGION_AREAS = {"EU": ["DEU", "FRA"], "IN": ["IND"], "AU": ["AUS"], "APAC": ["SGP", "JPN", "KOR"]}

def build_crosswalk():
    url = "https://www.bls.gov/soc/ISCO_SOC_Crosswalk.xls"
    print(f"crosswalk: downloading {url}")
    raw = requests.get(url, headers=UA, timeout=60).content
    df = pd.read_excel(io.BytesIO(raw), dtype=str, header=None)
    # locate the header row and the ISCO/SOC columns by content (layout drifts)
    isco_col = soc_col = name_col = None
    for r in range(min(12, len(df))):
        row = [str(x).strip().lower() for x in df.iloc[r].tolist()]
        for i, v in enumerate(row):
            if "isco" in v and "code" in v: isco_col = i
            if "isco" in v and ("title" in v or "description" in v): name_col = i
            if "soc" in v and "code" in v: soc_col = i
        if isco_col is not None and soc_col is not None:
            df = df.iloc[r + 1:]; break
    if isco_col is None or soc_col is None:
        raise SystemExit("Could not find ISCO/SOC code columns - inspect the xls header")
    seen, rows = set(), []
    for _, row in df.iterrows():
        isco = str(row[isco_col]).strip(); soc = str(row[soc_col]).strip()
        if not isco[:1].isdigit() or "-" not in soc: continue
        isco2 = isco.replace(".", "")[:2]
        name = str(row[name_col]).strip() if name_col is not None else ""
        key = (soc, isco2)
        if key in seen: continue
        seen.add(key); rows.append({"soc_code": soc, "isco2_code": isco2, "isco2_name": name})
    out = HERE / "soc_isco_crosswalk.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["soc_code", "isco2_code", "isco2_name"])
        w.writeheader(); w.writerows(rows)
    print(f"  wrote {out.name}: {len(rows)} SOC->ISCO2 rows")

def ilostat_isco2(area):
    url = ("https://rplumber.ilo.org/data/indicator/"
           f"?id=EMP_TEMP_SEX_OCU_NB_A&ref_area={area}&sex=SEX_T&format=.csv&timefrom=2021")
    r = requests.get(url, headers=UA, timeout=60); r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), dtype=str)
    # keep ISCO-08 2-digit classif rows, latest year, total sex
    cl = next(c for c in df.columns if c.lower().startswith("classif1"))
    tcol = next(c for c in df.columns if c.lower() in ("time", "year"))
    vcol = next(c for c in df.columns if c.lower() in ("obs_value", "value"))
    df = df[df[cl].str.contains("ISCO08_2", na=False)]
    df = df[df[tcol] == df[tcol].max()]
    out = {}
    for _, row in df.iterrows():
        code = row[cl].split("_")[-1]
        if len(code) == 2 and code.isdigit():
            out[code] = out.get(code, 0.0) + float(row[vcol]) * 1000.0  # ILOSTAT is in thousands
    return out

def build_employment(region):
    agg = {}
    for area in REGION_AREAS[region]:
        print(f"employment {region}: ILOSTAT {area}")
        for code, v in ilostat_isco2(area).items():
            agg[code] = agg.get(code, 0.0) + v
    out = HERE / f"{region}_employment.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["isco2_code", "isco2_name", "employment"])
        w.writeheader()
        for code in sorted(agg):
            w.writerow({"isco2_code": code, "isco2_name": "", "employment": round(agg[code])})
    print(f"  wrote {out.name}: {len(agg)} ISCO-2 groups")

if __name__ == "__main__":
    build_crosswalk()
    for region in REGION_AREAS:
        try:
            build_employment(region)
        except Exception as exc:
            print(f"  {region} employment failed ({exc}) - fill {region}_employment.csv manually from ILOSTAT")
    print("Done. Commit isco/*.csv, then run the build-regions-model workflow.")
