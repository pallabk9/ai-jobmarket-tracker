#!/usr/bin/env python3
"""
Generic regional builder for the AWA AI-impact occupation model.

Same engine as the UK model, taxonomy-agnostic. Give it a populated
region input (regions/<REGION>_occupations.csv) and it produces
data/<region>_occupations.json in the exact shape the dashboard reads,
plus a headline capability gap.

It invents NOTHING: every number is computed from the region input you
supply (task-time allocations, employment, adoption discount, amplification
multiplier) and the region-agnostic task_scores.csv. An empty/placeholder
input fails loudly rather than emitting fake data.

Usage:  python3 build_region.py US
        python3 build_region.py EU regions/EU_occupations.csv
"""
import csv, json, sys, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent.parent                      # netlify-site/
DATA = SITE / "data"
STANDARD_WEEK = 37.0                            # hours; matches UK model
WORKING_WEEKS = 47.0                            # paid weeks/year
TASKS = [f"T{i:02d}" for i in range(1, 19)]

def load_scores():
    s = {}
    for row in csv.DictReader((HERE / "task_scores.csv").open()):
        s[row["task_id"]] = float(row["ai_susceptibility_may2026"])
    if len(s) != 18:
        raise SystemExit("task_scores.csv must define all 18 task scores")
    return s

def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: build_region.py <REGION> [input.csv]")
    region = sys.argv[1].upper()
    inp = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "regions" / f"{region}_occupations.csv"
    susc = load_scores()

    rows = [r for r in csv.DictReader(inp.open())
            if r.get("occ_code") and not r["occ_code"].lstrip().startswith("#")]
    if not rows:
        raise SystemExit(f"{inp} has no populated occupation rows. Fill it from the "
                         f"region's taxonomy + employment data before building "
                         f"(see README.md). Refusing to emit fabricated data.")

    occ = []
    for r in rows:
        alloc = {t: float(r[t]) for t in TASKS}
        tot = sum(alloc.values())
        if abs(tot - 100.0) > 0.5:
            raise SystemExit(f"{r['occ_code']}: task allocations sum to {tot}, must be 100")
        disc = float(r["adoption_discount"]); mult = float(r["amplification_multiplier"])
        emp = float(r["employment"])
        raw = sum(alloc[t] * susc[t] for t in TASKS) / 100.0
        pi = raw * disc
        hrs = pi * STANDARD_WEEK
        occ.append({
            "soc": r["occ_code"], "title": r["occ_title"],
            "smg_code": r["group_code"], "smg": r["group_name"],
            "employment": round(emp), "discount": round(disc, 3),
            "raw": round(raw, 4), "pi": round(pi, 4),
            "hrs_week": round(hrs, 1), "annual_hrs": round(hrs * WORKING_WEEKS),
            "fte": round(hrs * emp / STANDARD_WEEK),
            "mult": mult, "combined_hrs": round(hrs * mult, 2),
            "tasks": {t: round(alloc[t]) for t in TASKS},
        })

    # aggregate to groups (employment-weighted)
    groups = {}
    for o in occ:
        g = groups.setdefault(o["smg_code"], {"code": o["smg_code"], "name": o["smg"],
                                              "count": 0, "emp": 0.0, "rw": 0.0, "pw": 0.0})
        g["count"] += 1; g["emp"] += o["employment"]
        g["rw"] += o["raw"] * o["employment"]; g["pw"] += o["pi"] * o["employment"]
    glist = []
    for g in sorted(groups.values(), key=lambda x: x["code"]):
        e = g["emp"] or 1
        glist.append({"code": g["code"], "name": g["name"], "count": g["count"],
                      "employment_000": round(g["emp"] / 1000),
                      "raw": round(g["rw"] / e, 4), "practical": round(g["pw"] / e, 4),
                      "hrs": round(g["pw"] / e * STANDARD_WEEK, 1)})

    total_emp = sum(o["employment"] for o in occ)
    out = {"region": region, "as_of": "May 2026 frontier",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": f"AWA AI Impact Assessment ({region} task-decomposition, May 2026 frontier)",
           "task_labels": {r["task_id"]: r["task_category"]
                           for r in csv.DictReader((HERE / "task_scores.csv").open())},
           "total_employment": round(total_emp), "n_occupations": len(occ),
           "groups": glist, "occupations": occ}
    DATA.mkdir(exist_ok=True)
    (DATA / f"{region.lower()}_occupations.json").write_text(json.dumps(out, separators=(",", ":")))

    mr = sum(g["raw"] * g["count"] for g in glist) / sum(g["count"] for g in glist)
    mp = sum(g["practical"] * g["count"] for g in glist) / sum(g["count"] for g in glist)
    print(f"{region}: {len(occ)} occupations, {len(glist)} groups, "
          f"capability gap {round((mr - mp) * 100, 2)}pp -> data/{region.lower()}_occupations.json")
    print("Next: wire the dashboard gap_chart for this region to the new groups "
          "(see build_uk_occupations.py for the current.json patch pattern).")

if __name__ == "__main__":
    main()
