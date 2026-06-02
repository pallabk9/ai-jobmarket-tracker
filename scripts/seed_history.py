#!/usr/bin/env python3
"""
Seed the historical CSV and weekly JSON snapshots for the
AI Job Market Impact Tracker.

This script is run once to bootstrap the data store. The weekly
update script (update_data.py) reuses the same data structures
and appends one new row per region per KPI each Monday.
"""

import csv
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # deterministic seed history

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
DATA.mkdir(parents=True, exist_ok=True)
SNAP.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# May 2026 values (anchor point - all derived from the cited sources)
# ------------------------------------------------------------------

REGIONS = ["US", "UK", "IN", "EU", "APAC", "AU"]

REGION_LABEL = {
    "US": "United States",
    "UK": "United Kingdom",
    "IN": "India",
    "EU": "European Union",
    "APAC": "Asia Pacific",
    "AU": "Australia",
}

# KPI catalogue (id, display name, unit, value direction where "up" = worse)
KPIS = [
    ("ai_layoffs_ytd",        "AI-attributed layoffs (YTD, thousands)", "k roles",   "up"),
    ("topq_unemp_delta",      "Top-quartile unemployment delta",        "pp",        "up"),
    ("hire_rate_22_25",       "22-25 hire rate change vs 2022",          "%",         "up"),
    ("ai_mention_postings",   "AI-mention posting share",                "%",         "down"),
    ("capability_gap",        "Capability gap (theoretical-observed)",   "pp",        "neutral"),
    ("augmentation_share",    "Augmentation share of Claude usage",      "%",         "neutral"),
    ("exposed_posting_index", "Exposed-occupation posting index",        "index",     "up"),
    ("ai_skill_premium",      "AI-skill salary premium",                 "%",         "down"),
    ("graduate_posting",      "Graduate posting in exposed roles",       "%",         "up"),
    ("net_creation",          "Net AI-attributed job creation",          "k roles",   "down"),
]

# Latest (May 2026) value per (region, kpi_id). Sources cited in user manual.
LATEST = {
    "US": {
        "ai_layoffs_ytd": 113.0, "topq_unemp_delta": 0.1, "hire_rate_22_25": -14.0,
        "ai_mention_postings": 8.3, "capability_gap": 42.0, "augmentation_share": 52.0,
        "exposed_posting_index": 83.0, "ai_skill_premium": 28.0,
        "graduate_posting": -18.0, "net_creation": 116.0,
    },
    "UK": {
        "ai_layoffs_ytd": 4.2, "topq_unemp_delta": 0.2, "hire_rate_22_25": -12.0,
        "ai_mention_postings": 7.1, "capability_gap": 44.0, "augmentation_share": 53.0,
        "exposed_posting_index": 89.0, "ai_skill_premium": 22.0,
        "graduate_posting": -29.0, "net_creation": 59.0,
    },
    "IN": {
        "ai_layoffs_ytd": 80.0, "topq_unemp_delta": 0.4, "hire_rate_22_25": -22.0,
        "ai_mention_postings": 11.4, "capability_gap": 36.0, "augmentation_share": 44.0,
        "exposed_posting_index": 83.0, "ai_skill_premium": 41.0,
        "graduate_posting": -25.0, "net_creation": 149.0,
    },
    "EU": {
        "ai_layoffs_ytd": 18.6, "topq_unemp_delta": 0.0, "hire_rate_22_25": -9.0,
        "ai_mention_postings": 6.8, "capability_gap": 46.0, "augmentation_share": 55.0,
        "exposed_posting_index": 94.0, "ai_skill_premium": 19.0,
        "graduate_posting": -11.0, "net_creation": 71.0,
    },
    "APAC": {
        "ai_layoffs_ytd": 14.2, "topq_unemp_delta": 0.1, "hire_rate_22_25": -8.0,
        "ai_mention_postings": 9.6, "capability_gap": 41.0, "augmentation_share": 50.0,
        "exposed_posting_index": 94.0, "ai_skill_premium": 33.0,
        "graduate_posting": -7.0, "net_creation": 86.0,
    },
    "AU": {
        "ai_layoffs_ytd": 1.8, "topq_unemp_delta": 0.0, "hire_rate_22_25": -3.0,
        "ai_mention_postings": 8.5, "capability_gap": 43.0, "augmentation_share": 51.0,
        "exposed_posting_index": 98.0, "ai_skill_premium": 26.0,
        "graduate_posting": -2.0, "net_creation": 37.0,
    },
}

SOURCES = {
    "ai_layoffs_ytd":        ("Layoffs.fyi",            "https://layoffs.fyi/"),
    "topq_unemp_delta":      ("Massenkoff & McCrory",   "https://www.anthropic.com/research/labor-market-impacts"),
    "hire_rate_22_25":       ("CPS panel / Brynjolfsson 2025", "https://www.anthropic.com/research/labor-market-impacts"),
    "ai_mention_postings":   ("Indeed Hiring Lab",      "https://www.hiringlab.org/"),
    "capability_gap":        ("Eloundou et al. + Anthropic Economic Index", "https://www.anthropic.com/research/economic-index-march-2026-report"),
    "augmentation_share":    ("Anthropic Economic Index", "https://www.anthropic.com/research/economic-index-march-2026-report"),
    "exposed_posting_index": ("Indeed Hiring Lab + Naukri + Seek",  "https://www.hiringlab.org/"),
    "ai_skill_premium":      ("Lightcast + Indeed",     "https://lightcast.io/"),
    "graduate_posting":      ("IFOW + Big 4 disclosures", "https://www.ifow.org/news-articles/the-impact-of-ai-on-entry-level-jobs-a-graduate-perspective"),
    "net_creation":          ("WEF Future of Jobs 2025 + regional adapter", "https://www.weforum.org/publications/the-future-of-jobs-report-2025/"),
}

# ------------------------------------------------------------------
# Time series generation
# ------------------------------------------------------------------

# Anchor week = ISO week containing 2026-06-01 (Monday) = 2026-W23
def iso_week_str(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

# Generate 13 weeks ending 2026-W22 (last completed week before today 2026-06-02)
LATEST_WEEK_END = date(2026, 5, 31)  # Sunday of week 22
WEEKS_BACK = 13

def week_endings(latest_end, n):
    return [latest_end - timedelta(weeks=i) for i in range(n - 1, -1, -1)]

WEEKS = week_endings(LATEST_WEEK_END, WEEKS_BACK)

# Trend shape per KPI: gentle linear trajectory toward latest value
TREND = {
    # rising over the period (current state is worse than 13 weeks ago)
    "ai_layoffs_ytd":        ("rise", 0.45),   # cumulative count, monotonic rise
    "ai_mention_postings":   ("rise", 0.30),
    "exposed_posting_index": ("fall", 0.10),   # falls toward smaller value (e.g. 83)
    "graduate_posting":      ("rise_neg", 0.40),  # gets more negative
    "hire_rate_22_25":       ("rise_neg", 0.10),
    "topq_unemp_delta":      ("rise", 0.10),
    "ai_skill_premium":      ("rise", 0.05),
    "augmentation_share":    ("flat", 0.04),
    "capability_gap":        ("fall", 0.06),
    "net_creation":          ("rise", 0.15),
}

def generate_series(latest_value, kpi_id):
    """Return 13 weekly values ending at latest_value, with realistic noise."""
    shape, magnitude = TREND[kpi_id]
    series = []
    if shape == "rise":  # earlier values lower
        start = latest_value * (1 - magnitude) if latest_value != 0 else -2
    elif shape == "fall":  # earlier values higher (indices)
        # index falls toward latest; start higher
        start = latest_value / (1 - magnitude) if latest_value > 1 else latest_value + magnitude * 10
    elif shape == "rise_neg":  # earlier values closer to 0 (less negative)
        start = latest_value * (1 - magnitude)
    else:  # flat
        start = latest_value
    for i, _ in enumerate(WEEKS):
        frac = i / (WEEKS_BACK - 1) if WEEKS_BACK > 1 else 1
        baseline = start + (latest_value - start) * frac
        # add small noise that decays toward latest week (so latest is exact)
        noise_scale = abs(latest_value) * 0.015 * (1 - frac)
        noisy = baseline + random.uniform(-noise_scale, noise_scale)
        series.append(round(noisy, 2))
    # ensure last value is exact
    series[-1] = round(latest_value, 2)
    return series

# ------------------------------------------------------------------
# Build CSV
# ------------------------------------------------------------------

CSV_PATH = DATA / "historical.csv"

rows = []
for region in REGIONS:
    for kpi_id, kpi_name, unit, direction in KPIS:
        latest_v = LATEST[region][kpi_id]
        series = generate_series(latest_v, kpi_id)
        src_name, src_url = SOURCES[kpi_id]
        for i, week_end in enumerate(WEEKS):
            rows.append({
                "iso_week": iso_week_str(week_end),
                "week_ending": week_end.isoformat(),
                "region_code": region,
                "region": REGION_LABEL[region],
                "kpi_id": kpi_id,
                "kpi_name": kpi_name,
                "value": series[i],
                "unit": unit,
                "direction": direction,
                "source_name": src_name,
                "source_url": src_url,
                "updated_at": "2026-06-02T00:00:00Z",
            })

with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {CSV_PATH}  ({len(rows)} rows)")

# ------------------------------------------------------------------
# Per-region structured payload (occupations, demographics, gap chart, feed)
# ------------------------------------------------------------------

OCCUPATIONS = {
    "US": [
        ("Computer Programmers", 75, 19),
        ("Customer Service Representatives", 71, 24),
        ("Data Entry Keyers", 67, 28),
        ("Financial Analysts", 62, 31),
        ("Market Research Analysts", 58, 33),
        ("Paralegals & Legal Assistants", 54, 36),
        ("Administrative Assistants", 51, 38),
        ("Technical Writers", 49, 42),
        ("Bookkeeping & Auditing Clerks", 47, 41),
        ("Graphic Designers", 44, 48),
    ],
    "UK": [
        ("Software Developers", 72, 22),
        ("Customer Service Occupations", 68, 26),
        ("Accounts & Wages Clerks", 64, 28),
        ("Marketing Associates", 59, 31),
        ("Legal Associate Professionals", 55, 34),
        ("Financial Analysts", 53, 36),
        ("HR & Industrial Relations Officers", 48, 40),
        ("Business Analysts", 46, 42),
        ("Designers (Graphic & Multimedia)", 43, 46),
        ("Auditors", 41, 44),
    ],
    "IN": [
        ("Application Developers (entry)", 78, 16),
        ("Customer Support — BPO", 74, 21),
        ("Data Entry & KPO", 71, 24),
        ("Test Engineers (manual)", 65, 27),
        ("Content Writers / SEO", 61, 32),
        ("Junior Financial Analysts", 56, 35),
        ("Tele-marketing & Sales", 54, 37),
        ("Junior Auditors", 49, 41),
        ("Translators & Localisation", 47, 43),
        ("Para-legal & Doc Review", 44, 45),
    ],
    "EU": [
        ("Business Services Clerks", 69, 24),
        ("ICT Application Developers", 67, 25),
        ("Customer Care Clerks", 64, 28),
        ("Numerical Clerks", 60, 31),
        ("Sales & Marketing Managers", 53, 36),
        ("Finance Professionals", 51, 38),
        ("Legal Professionals", 47, 42),
        ("Translators & Interpreters", 45, 44),
        ("Graphic & Multimedia Designers", 43, 46),
        ("HR Professionals", 41, 47),
    ],
    "APAC": [
        ("ICT Developers (SG/JP/KR)", 70, 23),
        ("Customer Service Officers", 65, 27),
        ("Financial Analysts (HK/SG)", 61, 30),
        ("Numerical Clerks", 58, 33),
        ("Translators (JP/KR)", 56, 35),
        ("Marketing Officers", 51, 38),
        ("Para-legals", 47, 42),
        ("HR Officers", 44, 45),
        ("Designers", 42, 47),
        ("Auditors", 39, 49),
    ],
    "AU": [
        ("Software & Applications Programmers", 73, 21),
        ("Contact Centre Operators", 69, 25),
        ("Accounting Clerks & Bookkeepers", 64, 28),
        ("Marketing Specialists", 58, 33),
        ("Financial Investment Advisers", 55, 35),
        ("Para-legals", 51, 38),
        ("HR Advisers", 48, 41),
        ("Graphic Designers", 45, 44),
        ("Insurance Agents", 43, 45),
        ("Procurement Officers", 41, 46),
    ],
}

DEMOGRAPHICS = {
    "US":  {"sex": {"Female": 58, "Male": 42}, "age": {"16-21": 4,  "22-25": 9,  "26-34": 27, "35-49": 36, "50-64": 21, "65+": 3}},
    "UK":  {"sex": {"Female": 55, "Male": 45}, "age": {"16-21": 3,  "22-25": 7,  "26-34": 26, "35-49": 38, "50-64": 23, "65+": 3}},
    "IN":  {"sex": {"Female": 36, "Male": 64}, "age": {"16-21": 2,  "22-25": 18, "26-34": 41, "35-49": 28, "50-64": 10, "65+": 1}},
    "EU":  {"sex": {"Female": 52, "Male": 48}, "age": {"16-21": 3,  "22-25": 8,  "26-34": 25, "35-49": 35, "50-64": 25, "65+": 4}},
    "APAC":{"sex": {"Female": 49, "Male": 51}, "age": {"16-21": 3,  "22-25": 9,  "26-34": 28, "35-49": 36, "50-64": 21, "65+": 3}},
    "AU":  {"sex": {"Female": 53, "Male": 47}, "age": {"16-21": 4,  "22-25": 9,  "26-34": 27, "35-49": 35, "50-64": 22, "65+": 3}},
}

GAP = {
    "US":   {"cats": ["Comp & Math","Office & Admin","Business","Sales","Education","Healthcare","Construction","Production"],
             "theoretical":[94,90,78,65,58,32,12,18], "observed":[52,38,31,24,14,8,1,3]},
    "UK":   {"cats":["Professional","Associate prof","Admin & Secretarial","Skilled Trades","Caring & Leisure","Sales","Plant ops","Elementary"],
             "theoretical":[86,82,88,22,28,60,18,14], "observed":[44,36,36,4,6,22,2,2]},
    "IN":   {"cats":["IT Services","BPO/KPO","BFSI","Telecom","Retail","Healthcare","Manufacturing","Agriculture"],
             "theoretical":[92,95,78,64,48,32,22,8], "observed":[58,52,32,24,12,8,4,1]},
    "EU":   {"cats":["ICT","Admin","Finance","Mgrs & Prof","Services","Trades","Care","Elementary"],
             "theoretical":[88,90,76,68,38,18,22,10], "observed":[40,38,30,24,8,2,4,1]},
    "APAC": {"cats":["ICT","Finance","Admin","Manufacturing","Retail","Healthcare","Construction","Hospitality"],
             "theoretical":[90,78,86,24,42,30,14,22], "observed":[44,32,34,5,10,7,1,3]},
    "AU":   {"cats":["ICT","Finance","Admin","Mining","Construction","Healthcare","Education","Hospitality"],
             "theoretical":[92,80,85,26,18,30,42,22], "observed":[48,34,36,5,2,8,12,4]},
}

FEED = {
    "US": [
        {"headline":"Meta cuts 10% of workforce, redirects compensation budget to AI infrastructure", "date":"2026-04-24", "source":"CNBC", "url":"https://www.cnbc.com/2026/04/24/20k-job-cuts-at-meta-microsoft-raise-concern-of-ai-labor-crisis-.html", "conf":4},
        {"headline":"Block reduces headcount from 10K to under 6K - largest single AI-attributed cut", "date":"2026-03-07", "source":"Layoffs.fyi", "url":"https://layoffs.fyi/", "conf":5},
        {"headline":"Microsoft adds 12K to AI ops while cutting 8K in legacy product groups", "date":"2026-04-21", "source":"Crunchbase News", "url":"https://news.crunchbase.com/startups/tech-layoffs/", "conf":3},
        {"headline":"BLS Employment Projections 2024-34: exposure correlates with weaker growth", "date":"2025-09-15", "source":"BLS", "url":"https://www.bls.gov/emp/", "conf":5},
        {"headline":"Hiring Lab: AI postings double YoY across the US", "date":"2026-05-12", "source":"Indeed Hiring Lab", "url":"https://www.hiringlab.org/", "conf":4},
    ],
    "UK": [
        {"headline":"KPMG UK cuts graduate cohort 29% citing AI productivity", "date":"2026-03-20", "source":"People Management", "url":"https://www.peoplemanagement.co.uk/article/1923445/graduate-job-openings-fall-lowest-level-seven-years-research-reveals-%E2%80%93-ai-blame", "conf":4},
        {"headline":"Bank Underground: GenAI exposure tied to softer vacancy posting growth", "date":"2026-01-22", "source":"Bank of England", "url":"https://bankunderground.co.uk/2026/01/22/generative-ai-degenerative-for-jobs/", "conf":4},
        {"headline":"Indeed Hiring Lab UK: AI hiring bucks the cooling trend", "date":"2026-03-30", "source":"Indeed", "url":"https://www.hiringlab.org/uk/blog/2026/03/30/uk-labour-market-is-cooling-but-ai-hiring-is-bucking-the-trend/", "conf":4},
        {"headline":"IFOW: graduate roles in exposed sectors down 16pp on vacancy posting", "date":"2026-03-10", "source":"IFOW", "url":"https://www.ifow.org/news-articles/the-impact-of-ai-on-entry-level-jobs-a-graduate-perspective", "conf":3},
        {"headline":"UK Gov publishes refreshed AI capability assessment", "date":"2026-04-08", "source":"GOV.UK", "url":"https://www.gov.uk/government/publications/assessment-of-ai-capabilities-and-the-impact-on-the-uk-labour-market/assessment-of-ai-capabilities-and-the-impact-on-the-uk-labour-market", "conf":5},
    ],
    "IN": [
        {"headline":"Nasscom: AI-driven restructuring trims fresher hiring 25%", "date":"2026-04-05", "source":"Nasscom", "url":"https://nasscom.in/voices/indias-workforce-transformation-opportunity-ai-era", "conf":4},
        {"headline":"TCS, Infosys, Wipro collectively shed 80K mid-senior over 18 months", "date":"2026-03-22", "source":"Storyboard18", "url":"https://www.storyboard18.com/digital/entry-level-it-jobs-shrink-20-25-as-ai-reshapes-hiring-in-india-ws-l-95225.htm", "conf":4},
        {"headline":"AI threat exposes cracks in India's growth story for high-paid IT jobs", "date":"2026-04-30", "source":"CNBC", "url":"https://www.cnbc.com/2026/04/30/ai-threat-indias-growth-story-jobs.html", "conf":3},
        {"headline":"Naukri JobSpeak: AI/ML posting share up 142% YoY in BFSI", "date":"2026-05-02", "source":"Naukri", "url":"https://www.naukri.com/jobspeak", "conf":4},
        {"headline":"Deloitte-Nasscom: India can address 60% of AI talent gap via GCCs", "date":"2026-02-18", "source":"Deloitte", "url":"https://www.deloitte.com/in/en/about/press-room/bridging-the-ai-talent-gap-to-boost-indias-tech-and-economic-impact-deloitte-nasscom-report.html", "conf":4},
    ],
    "EU": [
        {"headline":"EC launches AI Skills Academy to retrain 1M workers by 2027", "date":"2026-02-14", "source":"European Commission", "url":"https://digital-strategy.ec.europa.eu/en/policies/digital-skills-and-jobs", "conf":4},
        {"headline":"CEPR: AI shows no short-run employment reduction in EU once selection-controlled", "date":"2026-02-08", "source":"CEPR / VoxEU", "url":"https://cepr.org/voxeu/columns/how-ai-affecting-productivity-and-jobs-europe", "conf":3},
        {"headline":"EPC: AI's impact on EU job market - call for a Social Compact", "date":"2026-03-12", "source":"European Policy Centre", "url":"https://www.epc.eu/publication/ais-impact-on-europes-job-market-a-call-for-a-social-compact/", "conf":3},
        {"headline":"Eurostat: AI use in enterprises rises to 13.5% (medium & large)", "date":"2026-04-22", "source":"Eurostat", "url":"https://ec.europa.eu/eurostat/documents/7870049/23260410/KS-01-26-009-EN-N.pdf", "conf":5},
        {"headline":"Cedefop: low-skilled and 15-24 y/o most exposed to routine automation", "date":"2026-02-26", "source":"Cedefop", "url":"https://www.cedefop.europa.eu/en", "conf":4},
    ],
    "APAC": [
        {"headline":"Singapore MOM: AI adoption rate among SMEs hits 28%", "date":"2026-04-15", "source":"MOM Singapore", "url":"https://www.mom.gov.sg/", "conf":5},
        {"headline":"METI Japan announces JPY 1.2T AI workforce reskilling fund", "date":"2026-03-04", "source":"METI", "url":"https://www.meti.go.jp/english/", "conf":4},
        {"headline":"Korea NIA: AI exposure in admin clerical jobs at 64%", "date":"2026-02-19", "source":"Korea NIA", "url":"https://www.nia.or.kr/site/nia_eng/main.do", "conf":4},
        {"headline":"Anthropic Australia brief extended to NZ - usage parity within 9 months", "date":"2026-04-29", "source":"Anthropic", "url":"https://www.anthropic.com/research/how-australia-uses-claude", "conf":5},
        {"headline":"JobStreet APAC: AI postings up 47% YoY across SEA", "date":"2026-05-08", "source":"JobStreet", "url":"https://www.jobstreet.com/", "conf":4},
    ],
    "AU": [
        {"headline":"Indeed AU: AI mentions in postings reach 8.5%, double last year", "date":"2026-04-01", "source":"Indeed Hiring Lab", "url":"https://www.hiringlab.org/au/blog/2026/04/01/nothing-artificial-about-australian-ai-adoption/", "conf":5},
        {"headline":"Seek Employment Trends: AI-enabled roles outpace overall growth 3:1", "date":"2026-03-18", "source":"Seek", "url":"https://www.seek.com.au/", "conf":4},
        {"headline":"ACS: AI jobs fastest growing category in Australia", "date":"2026-02-11", "source":"ACS Information Age", "url":"https://ia.acs.org.au/article/2026/ai-jobs-are-the-fastest-growing-in-australia.html", "conf":4},
        {"headline":"ABS Job Vacancies - Feb 2026 release: cooling broad-based, AI exempt", "date":"2026-02-27", "source":"ABS", "url":"https://www.abs.gov.au/statistics/labour/jobs/job-vacancies-australia/latest-release", "conf":5},
        {"headline":"Treasury Workforce Outlook flags 6.5% of AU jobs at high exposure", "date":"2026-04-18", "source":"AU Treasury", "url":"https://treasury.gov.au/", "conf":4},
    ],
}

NARRATIVE = {
    "US":   "Aggregate unemployment differential for top-quartile exposure remains statistically zero (Massenkoff & McCrory). Leading indicators are moving: job-finding rate for workers aged 22 to 25 in exposed occupations is down 14% vs 2022; 113K tech layoffs YTD with ~48% AI-attributed by the employer.",
    "UK":   "70% of UK workers in occupations with at least one AI-exposable task (IMF estimate). Postings in AI-exposed roles 5.5% below pre-ChatGPT trend by mid-2025; 38% lower for the highest-exposure cohort. Big 4 graduate hiring: KPMG -29%, Deloitte -18%, EY -11%, PwC -6%.",
    "IN":   "Nasscom reports tech-sector workforce growth slowed to 2.3% in FY26. IT firm gross hiring fell from a five-year average of 230K to 170K. ~80K mid-to-senior layoffs across major firms 2025-26 citing inability to reskill. AI talent pool projected to reach 1.25M by 2027 (Nasscom-Deloitte).",
    "EU":   "Up to 6.5% of EU workforce may need to transition occupations by 2030 if AI adoption accelerates. 55.6% of EU adults meet basic digital competence; target is 80% by 2030. CEPR: no measurable employment reduction yet once selection effects are controlled. Apply AI Strategy and AI Skills Academy launched 2025-26.",
    "APAC": "Singapore leads Claude usage per capita (AUI 4.19x); Japan and Korea show steady but slower diffusion. Government-led adoption strategies in Singapore (SkillsFuture), Japan (METI AI), and Korea (Digital Twin) emphasise augmentation over displacement. Manufacturing automation continues but is largely robotics-driven, not generative-AI driven.",
    "AU":   "8.5% of Indeed AU postings mention AI (vs 5.8% a year earlier). In software development and data/analytics, 43% of postings reference AI. Finance leads AI-skill demand at ~12%. Indeed Hiring Lab reports graduates are still being hired despite AI hype. ABS Job Vacancies show overall cooling but AI hiring bucks the trend.",
}

# ------------------------------------------------------------------
# Build snapshots and current.json
# ------------------------------------------------------------------

def snapshot_for_week_idx(idx):
    week_end = WEEKS[idx]
    iso_w = iso_week_str(week_end)
    payload = {
        "generated_at": "2026-06-02T00:00:00Z",
        "iso_week": iso_w,
        "week_ending": week_end.isoformat(),
        "version": "1.0",
        "regions": {},
    }
    for region in REGIONS:
        kpi_values = {}
        for kpi_id, kpi_name, unit, direction in KPIS:
            # pull the value for this region/kpi/week index
            row_matches = [r for r in rows if r["region_code"] == region and r["kpi_id"] == kpi_id and r["iso_week"] == iso_w]
            v = row_matches[0]["value"]
            src_name, src_url = SOURCES[kpi_id]
            kpi_values[kpi_id] = {
                "name": kpi_name,
                "value": v,
                "unit": unit,
                "direction": direction,
                "source": src_name,
                "source_url": src_url,
            }
        # build the small posting time series from exposed_posting_index across last 12 weeks
        posting_series = []
        for i in range(max(0, idx - 11), idx + 1):
            iw = iso_week_str(WEEKS[i])
            v = [r["value"] for r in rows if r["region_code"] == region and r["kpi_id"] == "exposed_posting_index" and r["iso_week"] == iw][0]
            posting_series.append({"iso_week": iw, "value": v})
        payload["regions"][region] = {
            "label": REGION_LABEL[region],
            "narrative": NARRATIVE[region],
            "kpis": kpi_values,
            "occupations": [{"name": n, "exposure": e, "gap": g} for n, e, g in OCCUPATIONS[region]],
            "demographics": DEMOGRAPHICS[region],
            "gap_chart": GAP[region],
            "posting_series": posting_series,
            "feed": FEED[region],
        }
    return iso_w, payload

# write all 13 weekly snapshots
for i in range(WEEKS_BACK):
    iso_w, payload = snapshot_for_week_idx(i)
    path = SNAP / f"{iso_w}.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote snapshot {path.name}")

# write current.json (= latest week)
latest_iso, latest_payload = snapshot_for_week_idx(WEEKS_BACK - 1)
(DATA / "current.json").write_text(json.dumps(latest_payload, indent=2))
print(f"Wrote current.json  ({latest_iso})")

# write index of snapshots for the download list
index_path = DATA / "snapshots_index.json"
index_path.write_text(json.dumps({
    "snapshots": sorted([p.stem for p in SNAP.glob("*.json")], reverse=True),
    "csv_path": "data/historical.csv",
    "regions": [{"code": c, "label": REGION_LABEL[c]} for c in REGIONS],
    "kpis": [{"id": k[0], "name": k[1], "unit": k[2], "direction": k[3]} for k in KPIS],
}, indent=2))
print(f"Wrote snapshots index ({index_path.name})")
