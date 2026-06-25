#!/usr/bin/env python3
"""Build the user manual PDF for the AI Job Market Impact Tracker."""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, ListFlowable, ListItem, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "manual.pdf"

# ---- AWA brand palette (Brand book, May 2026) ----
# Coral, Midnight, Mint, Sky, Dusk, Light. White-led layouts; Coral is accent only (<10%).
MIDNIGHT = colors.HexColor("#253746")   # primary ink, headings, dark grounds (never pure black)
CORAL    = colors.HexColor("#FF5C39")   # accent: logo, key data, punctuation
CORAL_D  = colors.HexColor("#E8431F")
MINT     = colors.HexColor("#11998A")   # readable mint for positive text
SKY      = colors.HexColor("#3E94A8")   # secondary data accent
DUSK     = colors.HexColor("#6F58A0")
LIGHT    = colors.HexColor("#D9E1E2")   # neutral lines / section fills
LIGHT2   = colors.HexColor("#EAEEEF")
WHITE    = colors.white
DARKMUTE = colors.HexColor("#C7D0D6")   # muted text on Midnight grounds

# Legacy aliases mapped onto the AWA palette (keeps downstream references working)
NAVY  = MIDNIGHT
BLUE  = MIDNIGHT
INK   = MIDNIGHT
MUTED = colors.HexColor("#5A6B78")
LINE  = LIGHT
LINE2 = LIGHT2
GOOD  = MINT
WARN  = CORAL
BAD   = CORAL_D

# Styles
ss = getSampleStyleSheet()

# AWA brand type is Spectral (serif display) + Manrope (sans). Those TTFs are not in the
# repo, so we use the brand's documented fallbacks: a serif for Spectral, Helvetica for
# Manrope. If the real fonts are added to assets/fonts, register them and swap the names below.
SERIF   = "Times-Roman"
SERIF_B = "Times-Bold"
SERIF_I = "Times-Italic"
SANS    = "Helvetica"
SANS_B  = "Helvetica-Bold"
SANS_O  = "Helvetica-Oblique"

# Body — Spectral (serif) for the section title, Manrope (sans) for everything else.
h1 = ParagraphStyle("h1", parent=ss["Heading1"],
    fontName=SERIF_B, fontSize=19, textColor=MIDNIGHT,
    leading=23, spaceBefore=16, spaceAfter=8, keepWithNext=1)
h2 = ParagraphStyle("h2", parent=ss["Heading2"],
    fontName=SANS_B, fontSize=12.5, textColor=MIDNIGHT,
    leading=17, spaceBefore=12, spaceAfter=5, keepWithNext=1)
h3 = ParagraphStyle("h3", parent=ss["Heading3"],
    fontName=SANS_B, fontSize=10.5, textColor=CORAL,
    leading=14, spaceBefore=10, spaceAfter=3, keepWithNext=1)
body = ParagraphStyle("body", parent=ss["Normal"],
    fontName=SANS, fontSize=10, textColor=MIDNIGHT,
    leading=14.5, spaceAfter=6, alignment=TA_JUSTIFY)
bullet_style = ParagraphStyle("bullet", parent=body, leftIndent=16, bulletIndent=4,
    spaceAfter=3, bulletColor=CORAL, bulletFontName=SANS_B)
small = ParagraphStyle("small", parent=body, fontSize=9, textColor=MUTED, leading=12)
note = ParagraphStyle("note", parent=body, fontName=SERIF_I, textColor=MUTED)
mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=9,
                       textColor=MIDNIGHT, leading=12, leftIndent=10)

# ---------------- AWA LOGO (vector reproduction of the supplied master lockup) ----------------
def draw_awa_logo(c, x, y, dia, dark_bg=False):
    """AWA horizontal lockup: A.W.A coral marque + rule + 'DNA of work'.
    x = left edge, y = vertical centre, dia = bubble diameter in points."""
    r = dia / 2.0
    s = 1.78 * r
    centers = [x + r + i * s for i in range(3)]
    c.saveState()
    c.setFillColor(CORAL)
    nh = 0.60 * dia
    for i in range(2):
        c.rect(centers[i], y - nh / 2.0, centers[i + 1] - centers[i], nh, stroke=0, fill=1)
    for cx in centers:
        c.circle(cx, y, r, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", dia * 0.58)
    for cx, ch in zip(centers, ["A", "W", "A"]):
        c.drawCentredString(cx, y - dia * 0.205, ch)
    rule_x = centers[-1] + r + 0.55 * dia
    c.setStrokeColor(WHITE if dark_bg else MIDNIGHT)
    c.setLineWidth(max(0.7, dia * 0.045))
    c.line(rule_x, y - 0.72 * r, rule_x, y + 0.72 * r)
    tx = rule_x + 0.55 * dia
    ts = dia * 0.72
    c.setFillColor(WHITE if dark_bg else MIDNIGHT)
    base = y - ts * 0.34
    c.setFont("Helvetica-Bold", ts); c.drawString(tx, base, "DNA")
    tx += c.stringWidth("DNA", "Helvetica-Bold", ts) + ts * 0.22
    c.setFont("Times-Italic", ts); c.drawString(tx, base, "of")
    tx += c.stringWidth("of", "Times-Italic", ts) + ts * 0.22
    c.setFont("Helvetica", ts); c.drawString(tx, base, "work")
    c.restoreState()

# ---------------- PAGE TEMPLATES ----------------
def on_cover(canvas, doc):
    c = canvas
    W, H = A4
    M = 1.8 * cm
    c.saveState()
    c.setFillColor(MIDNIGHT); c.rect(0, 0, W, H, stroke=0, fill=1)
    # signature coral dots, descending top-right
    c.setFillColor(CORAL)
    for yy in (H - 3.1 * cm, H - 3.95 * cm, H - 4.8 * cm):
        c.circle(W - 1.5 * cm, yy, 3.0, stroke=0, fill=1)
    # reversed logo, top-left
    draw_awa_logo(c, M, H - 2.15 * cm, 15, dark_bg=True)
    c.setFont("Helvetica", 8.5); c.setFillColor(DARKMUTE)
    c.drawRightString(W - 1.5 * cm, H - 2.02 * cm, "USER MANUAL     v1.0     JUNE 2026")
    # kicker (Spectral italic, coral)
    c.setFont("Times-Italic", 16); c.setFillColor(CORAL)
    c.drawString(M, H * 0.63, "The DNA of work")
    # title (Spectral bold, white)
    c.setFillColor(WHITE); c.setFont("Times-Bold", 35)
    c.drawString(M, H * 0.63 - 1.2 * cm, "AI Job Market")
    c.drawString(M, H * 0.63 - 2.4 * cm, "Impact Tracker")
    # subtitle
    c.setFont("Helvetica", 15); c.setFillColor(LIGHT)
    c.drawString(M, H * 0.63 - 3.5 * cm, "User manual")
    c.setStrokeColor(CORAL); c.setLineWidth(1.4)
    c.line(M, H * 0.63 - 3.95 * cm, M + 4.6 * cm, H * 0.63 - 3.95 * cm)
    # description
    c.setFont("Helvetica", 10.5); c.setFillColor(DARKMUTE)
    desc = ["How the dashboard works, what every term means,",
            "and where every number comes from.",
            "Grounded in the Anthropic Observed Exposure methodology.",
            "Six regions  -  weekly refresh."]
    yy = H * 0.63 - 4.8 * cm
    for ln in desc:
        c.drawString(M, yy, ln); yy -= 0.55 * cm
    # byline
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 13)
    c.drawString(M, 3.3 * cm, "Developed by AWA")
    c.setFillColor(DARKMUTE); c.setFont("Helvetica", 9.5)
    c.drawString(M, 3.3 * cm - 0.52 * cm, "Advanced Workplace Associates     Research instrument")
    # baseline rule + footer
    c.setStrokeColor(colors.HexColor("#33485A")); c.setLineWidth(0.8)
    c.line(M, 2.15 * cm, W - M, 2.15 * cm)
    c.setFillColor(DARKMUTE); c.setFont("Helvetica", 8)
    c.drawString(M, 1.65 * cm, "Version 1.0  -  June 2026")
    c.drawRightString(W - M, 1.65 * cm, "It's in our DNA")
    c.restoreState()

def on_page(canvas, doc):
    c = canvas
    W, H = A4
    M = 1.8 * cm
    c.saveState()
    # header: small logo left, running title right, hairline under
    draw_awa_logo(c, M, H - 1.15 * cm, 8.5, dark_bg=False)
    c.setFont("Helvetica", 8); c.setFillColor(MUTED)
    c.drawRightString(W - M, H - 1.2 * cm, "AI Job Market Impact Tracker     User manual")
    c.setStrokeColor(LIGHT); c.setLineWidth(0.8)
    c.line(M, H - 1.5 * cm, W - M, H - 1.5 * cm)
    # footer: byline left, tagline centre, page right, hairline above
    c.line(M, 1.4 * cm, W - M, 1.4 * cm)
    c.setFont("Helvetica", 8); c.setFillColor(MUTED)
    c.drawString(M, 1.0 * cm, "Developed by AWA")
    c.setFillColor(CORAL); c.drawCentredString(W / 2.0, 1.0 * cm, "The DNA of work")
    c.setFillColor(MUTED); c.drawRightString(W - M, 1.0 * cm, "Page %d" % doc.page)
    c.restoreState()

def bullets(items):
    paras = [ListItem(Paragraph(t, bullet_style), leftIndent=12) for t in items]
    return ListFlowable(paras, bulletType="bullet", bulletChar="•", leftIndent=12, spaceBefore=2, spaceAfter=6)

def kv_table(rows, col_widths=None):
    tdata = []
    for label, value in rows:
        tdata.append([Paragraph(f"<b>{label}</b>", small), Paragraph(value, small)])
    t = Table(tdata, colWidths=col_widths or [4.0 * cm, 12.0 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LINEBELOW", (0,0), (-1,-2), 0.4, LINE),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4),
    ]))
    return t

def header_table(header, rows, col_widths):
    tdata = [[Paragraph(f"<b>{c}</b>", ParagraphStyle("th", parent=small, textColor=colors.white)) for c in header]]
    for r in rows:
        tdata.append([Paragraph(c, small) for c in r])
    t = Table(tdata, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT2, colors.white]),
        ("GRID", (0,0), (-1,-1), 0.4, LINE),
    ]))
    return t

# ------------------------------------------------------------------
# CONTENT
# ------------------------------------------------------------------

story = []

# ----- Cover (rendered entirely by on_cover) -----
story.append(Spacer(1, 2))
story.append(PageBreak())

# ----- 1. Introduction -----
story.append(Paragraph("1. What this tool is", h1))
story.append(Paragraph(
    "The AI Job Market Impact Tracker is a research instrument that turns disparate signals "
    "about AI's effect on labour markets into a single, weekly-refreshed evidence base, "
    "viewable as a dashboard and downloadable as raw data. It covers six regions: "
    "the United States, United Kingdom, India, European Union, Asia Pacific, and Australia.",
    body))
story.append(Paragraph(
    "It exists because the public debate about AI and jobs lurches between two extremes "
    "&mdash; nothing is changing, or everything is. The reality, as Anthropic's own research "
    "shows, is that the early signals are subtle, narrow, and easy to miss in aggregate "
    "statistics. The tracker is built to detect those signals as they emerge.",
    body))

story.append(Paragraph("1.1 Who it is for", h2))
story.append(Paragraph(
    "Workplace strategy consultants, workforce planners at large employers, policy researchers, "
    "and journalists who need an accountable, sourced view of how the labour market is shifting.",
    body))

story.append(Paragraph("1.2 What it is not", h2))
story.append(bullets([
    "It is not an oracle. It cannot predict which individual will lose a job.",
    "It is not a causal claim. It tracks correlations and attributes events to AI only where the employer or a credible source says so.",
    "It is not investment or hiring advice. It is a research tool.",
]))

# ----- 2. Background research -----
story.append(Paragraph("2. Background research &mdash; what the methodology is built on", h1))
story.append(Paragraph(
    "Massenkoff and McCrory (Anthropic, 5 March 2026) published a paper titled "
    "<i>Labor market impacts of AI: A new measure and early evidence</i>. "
    "It introduced a metric they called <b>Observed Exposure</b>, designed to measure not just "
    "which jobs are theoretically vulnerable to AI but which are already, in practice, being "
    "done by AI in real-world traffic.",
    body))

story.append(Paragraph("2.1 The three inputs", h2))
story.append(Paragraph(
    "Observed Exposure combines three independent data sources:",
    body))
story.append(bullets([
    "<b>O*NET</b>: the US Department of Labor's database of around 800 occupations, each decomposed into specific tasks.",
    "<b>Eloundou et al. (2023)</b>: an academic paper that scored every O*NET task on a 0 / 0.5 / 1 scale (called &beta;) for its theoretical exposure to LLM speed-up.",
    "<b>The Anthropic Economic Index</b>: real-world usage data showing what tasks Claude is actually being asked to do, and whether the use is automated (AI does the work) or augmentative (human and AI collaborate).",
]))

story.append(Paragraph("2.2 The headline findings (US, as of March 2026)", h2))
story.append(bullets([
    "97% of observed Claude task usage falls into categories Eloundou et al. rated as theoretically feasible (&beta; &ge; 0.5).",
    "The most exposed US occupations are <b>Computer Programmers (75%)</b>, <b>Customer Service Representatives</b>, <b>Data Entry Keyers (67%)</b>, and <b>Financial Analysts</b>.",
    "30% of US workers have zero exposure under this measure &mdash; their tasks appeared too infrequently in Claude usage to count.",
    "BLS 2024-2034 employment projections fall by 0.6 percentage points for every 10 pp of additional Observed Exposure.",
    "Top-quartile-exposure US workers are more likely to be female (+16 pp), more educated, older, and earn 47% more than the unexposed group.",
    "Aggregate unemployment in the top-quartile-exposure group has not increased significantly since late 2022, though the job-finding rate for workers aged 22 to 25 in exposed occupations has dropped about 14%.",
]))

story.append(Paragraph(
    "Massenkoff and McCrory's central message is one of analytical modesty: AI's labour-market "
    "impact may be like the internet or trade with China rather than like the COVID shock. "
    "If so, it will not be obvious from headline unemployment numbers. A measure that tracks the "
    "narrowing gap between theoretical capability and observed deployment is more likely to "
    "detect the inflection early.",
    body))

# ----- 3. The Observed Exposure score, step by step -----
story.append(Paragraph("3. How Observed Exposure is calculated", h1))
story.append(Paragraph(
    "The score is built bottom-up from tasks to occupations to occupation categories.",
    body))

story.append(Paragraph("3.1 Task level", h2))
story.append(Paragraph(
    "Every O*NET task receives three flags:",
    body))
story.append(bullets([
    "<b>&beta;</b> from Eloundou et al.: 0, 0.5, or 1.",
    "<b>Observed usage</b>: does this task appear with sufficient frequency in the Anthropic Economic Index, and is it work-related?",
    "<b>Use pattern</b>: of the observed usage, what share is automation versus augmentation?",
]))
story.append(Paragraph(
    "A task's coverage equals 1 if &beta; &ge; 0.5 <i>and</i> it has sufficient work-related Claude usage, "
    "weighted by 1.0 for automation and 0.5 for augmentation. Otherwise, coverage = 0.",
    body))

story.append(Paragraph("3.2 Occupation level", h2))
story.append(Paragraph(
    "An occupation's Observed Exposure is the time-weighted average of its task-level coverage scores. "
    "Time weights come from O*NET's reported time-on-task data: tasks workers spend more of their day "
    "on count more.",
    body))

story.append(Paragraph("3.3 Sector and regional aggregates", h2))
story.append(Paragraph(
    "Occupation scores are aggregated to occupation categories (e.g., Computer &amp; Math, Office &amp; Admin) "
    "by current employment weight. For regions other than the US, the local occupation classification "
    "is crosswalked to O*NET-SOC first; where local time-on-task data exists, it replaces the US weights.",
    body))

story.append(Paragraph(
    "<b>Robustness check.</b> The Anthropic paper varies several judgement calls "
    "(the &beta; coding, the automation weight, the usage threshold) and reports that the Spearman "
    "rank correlation of occupation-level exposures across reasonable parameterisations is very high. "
    "The ranking is stable even when the absolute numbers move.",
    body))

# ----- 4. KPI catalogue -----
story.append(Paragraph("4. The KPI catalogue", h1))
story.append(Paragraph(
    "The dashboard shows ten KPIs per region. Each KPI has a definition, a formula or source, "
    "a refresh cadence, and an alert band that triggers escalation in the weekly digest.",
    body))

kpis = [
    ("AI-attributed layoffs (YTD)",
     "Cumulative layoffs since 1 January where the employer cited AI. Measured for the US from the Challenger, Gray &amp; Christmas monthly Job Cut Report; other regions remain modelled pending a comparable source.",
     "Challenger, Gray &amp; Christmas monthly report (US, measured); Layoffs.fyi tracker as context.",
     "Monthly report, checked weekly.",
     "More than 500 in a single week."),
    ("Early-career unemployment delta (proxy)",
     "Youth minus overall unemployment rate, in percentage points, seasonally adjusted. A documented proxy for the top-quartile-exposure cohort: statistics agencies do not publish unemployment by AI exposure, so the original Massenkoff &amp; McCrory diff-in-diff can only be replicated from CPS microdata. Measured: US 20-24 (BLS), UK 18-24 (ONS), EU under-25 (Eurostat), AU 15-24 (ABS).",
     "BLS CPS, ONS LMS, Eurostat une_rt_m, ABS Labour Force; Massenkoff &amp; McCrory 2026 framing.",
     "Monthly.",
     "More than 0.5 pp rise in the differential over 13 weeks."),
    ("22-25 hire rate",
     "Year-on-year change in the monthly job-start rate among workers aged 22 to 25 in exposed occupations.",
     "BLS CPS panel, ONS LFS, equivalent for each region. Brynjolfsson, Chandar &amp; Chen (2025) provide the methodology template.",
     "Monthly.",
     "More than 10% YoY drop."),
    ("AI-mention posting share",
     "Percentage of job postings whose description references AI, ML, GenAI, prompt engineering, or related skills.",
     "Indeed Hiring Lab feeds, supplemented by Naukri JobSpeak (India) and Seek (Australia).",
     "Weekly.",
     "Doubling YoY."),
    ("Capability gap",
     "Theoretical &beta; (Eloundou) minus Observed Exposure, averaged across the region's occupations weighted by current employment. Expressed in percentage points.",
     "Eloundou et al. 2023 plus Anthropic Economic Index.",
     "Monthly.",
     "Gap closes by more than 3 pp."),
    ("Augmentation share",
     "Percentage of Claude conversations in the region's traffic mix classified as collaborative (augmentative) rather than end-to-end (automated).",
     "Anthropic Economic Index quarterly release.",
     "Quarterly.",
     "Below 45% or above 60%."),
    ("Exposed-occupation posting index",
     "Volume of job postings in the top-quartile-exposure occupations, indexed to a base of 100 in January 2025.",
     "Indeed Hiring Lab plus Naukri JobSpeak and Seek; ONS Vacancy Survey for UK validation.",
     "Weekly.",
     "More than 5% drop on a 4-week rolling basis."),
    ("AI-skill salary premium",
     "Median advertised salary for postings mentioning AI minus median for comparable non-AI postings, expressed as a percentage of the non-AI median.",
     "Indeed Hiring Lab plus Lightcast (formerly Burning Glass).",
     "Monthly.",
     "Premium widens or narrows by more than 10%."),
    ("Graduate posting",
     "Year-on-year change in entry-level postings in exposed roles. Big 4 graduate disclosures (KPMG, Deloitte, EY, PwC) are incorporated where published.",
     "Indeed Hiring Lab, IFOW graduate study, employer filings.",
     "Quarterly.",
     "More than 15% YoY drop."),
    ("Net AI-attributed job creation",
     "New AI, ML, data, security postings minus AI-attributed displacement events over the latest 12 months, in thousands of roles.",
     "WEF Future of Jobs 2025 regional baseline plus posting-derived adjustments.",
     "Quarterly.",
     "Net swings into negative territory."),
]
for name, definition, source, refresh, alert in kpis:
    story.append(Paragraph(name, h3))
    story.append(kv_table([
        ("Definition", definition),
        ("Source", source),
        ("Refresh", refresh),
        ("Alert band", alert),
    ]))
    story.append(Spacer(1, 4))

# ----- 5. How to read each panel -----
story.append(PageBreak())
story.append(Paragraph("5. How to read each dashboard panel", h1))

panels = [
    ("Most exposed occupations table",
     "Ten occupations in the selected region with the highest Observed Exposure score. "
     "The blue bar is the score itself, 0 to 100%. The red bar is the capability gap "
     "&mdash; how much room the score has to grow before reaching theoretical &beta; ceiling. "
     "When the red bar shrinks week on week without the blue bar staying flat, that is the "
     "earliest signal AI is moving deeper into that occupation."),
    ("Net job change (created vs displaced)",
     "A horizontal bar chart of jobs created (green) and displaced (red) over the last 12 months, "
     "by occupation family, in thousands of roles. Displacement figures filter to attribution-confidence "
     "of 3 or higher, so vague \"AI-driven\" press claims do not dominate. Use the source &amp; method "
     "tab on the card to see which buckets the figures roll up from."),
    ("Demographics in the exposed quartile",
     "A doughnut chart of the age distribution of workers in the top-quartile-exposure occupations. "
     "The chart subtitle shows the female/male split. Compare across regions to see how exposure "
     "concentrates differently &mdash; for example, the Indian top-quartile skews far younger "
     "than the European one."),
    ("Augmentation vs automation",
     "A doughnut chart showing the share of Claude usage in the region that is collaborative versus "
     "end-to-end. A high augmentation share suggests workers are still in the loop; a high automation "
     "share suggests AI is doing more of the work alone. Anthropic's March 2026 release shows "
     "augmentation just over half of Claude.ai conversations."),
    ("Posting volume in exposed roles",
     "A 12-week indexed line showing how postings in the top-quartile-exposure occupations are moving. "
     "Base = 100 at the first week shown. A downward slope of more than 5% over a 4-week rolling window "
     "is the alert band."),
    ("Capability gap by sector",
     "Twin bars per sector: blue is theoretical &beta;, red is Observed Exposure. The space between is "
     "headroom. This is the chart to watch over months and quarters &mdash; if red moves toward blue "
     "in a sector, that sector is converting capability into deployment."),
    ("News &amp; events feed",
     "Most recent AI-attributed events in the region. Each is tagged with an attribution-confidence "
     "score: 5 = company filing or direct statement; 4 = first-party data such as Indeed or Naukri; "
     "3 = credible reporting; 2 = secondary reporting; 1 = unsourced. Filter mentally to confidence "
     "&ge; 3 unless you are specifically tracking the narrative."),
]
for title, txt in panels:
    story.append(Paragraph(title, h3))
    story.append(Paragraph(txt, body))

# ----- 6. Regional adaptations -----
story.append(PageBreak())
story.append(Paragraph("6. Regional adaptations", h1))
story.append(Paragraph(
    "Observed Exposure was calibrated on US O*NET tasks and US Claude traffic. "
    "Three adaptations let it work consistently across the six regions:",
    body))
story.append(bullets([
    "<b>Crosswalking</b>: the local occupation classification is mapped to O*NET-SOC. UK uses SOC2020 (ONS crosswalk), India uses NCO-2015 (Nasscom crosswalk), the EU uses ISCO-08 (CEDEFOP crosswalk), Australia and New Zealand use ANZSCO 2022.",
    "<b>Time-use reweighting</b>: where local time-on-task data exists, it replaces the US weights. For India, this is rare; for the EU, Eurostat LFS provides partial coverage.",
    "<b>Country brief substitution</b>: Anthropic has published country briefs for India and Australia and is rolling out more. Where a brief exists, its task-mix is used in place of global Claude data.",
]))
story.append(Paragraph(
    "<b>Important caveat for cross-region reading.</b> Anthropic country briefs measure what Claude users "
    "in that country are doing &mdash; not what the country's workforce is doing. Cross-country comparisons "
    "should always use the within-country quartile rank as the primary comparable; absolute coverage "
    "is shown alongside as context only.",
    body))

table_data = [
    ["United States",    "O*NET-SOC native",      "BLS CPS, JOLTS, EP-2024-34",         "Indeed Hiring Lab, Lightcast, layoffs.fyi"],
    ["United Kingdom",   "SOC2020 → O*NET",       "ONS LFS, Vacancy Survey, IFOW",       "Indeed Hiring Lab UK, LinkedIn Economic Graph UK"],
    ["India",            "NCO-2015 → O*NET",      "NSO PLFS, Nasscom Strategic Review",  "Naukri JobSpeak weekly, Foundit"],
    ["European Union",   "ISCO-08 → O*NET",       "Eurostat LFS, Cedefop Skills Forecast","EURES, LinkedIn EU Economic Graph"],
    ["Asia Pacific",     "Mixed (SSOC, JSCO, KSCO)","Singapore MOM, Japan MHLW, Korea KOSIS","JobStreet, Jobsdb, Wantedly"],
    ["Australia",        "ANZSCO 2022",           "ABS Job Vacancies, Treasury",         "Indeed Hiring Lab AU, Seek Employment Trends"],
]
story.append(header_table(
    ["Region", "Classification", "Statistical baseline", "Real-time signal"],
    table_data, [3.0*cm, 4.0*cm, 5.0*cm, 5.0*cm]
))

# ----- 7. Data sources and refresh -----
story.append(Paragraph("7. Data sources and refresh cadence", h1))
story.append(Paragraph(
    "Sources are tiered by reliability and latency. Lower tiers are used to colour and accelerate, "
    "never to overwrite higher-tier numbers.",
    body))

tiers = [
    ["Tier 1 — Methodological anchor", "Anthropic Economic Index releases; Anthropic country briefs; Hugging Face dataset Anthropic/EconomicIndex.", "Quarterly", "Sets Observed Exposure per occupation."],
    ["Tier 2 — Official statistics", "US BLS, UK ONS, Eurostat, India NSO, Australia ABS, Singapore MOM.", "1-3 months", "Baseline employment, unemployment, demographics."],
    ["Tier 3 — Real-time market", "Indeed Hiring Lab, LinkedIn Economic Graph, Seek, Naukri JobSpeak, Lightcast.", "Weekly", "Postings, AI-mention share, vacancy trends."],
    ["Tier 4 — Narrative & event", "Layoffs.fyi, WEF Future of Jobs, McKinsey/IFOW/British Progress reports, central-bank notes.", "Weekly-annual", "AI-attributed layoffs, narrative, alternative attributions."],
]
story.append(header_table(["Tier", "Sources", "Latency", "Role"], tiers,
    [4.5*cm, 6.5*cm, 2.2*cm, 3.8*cm]))

story.append(Paragraph("7.1 Refresh cycle", h2))
story.append(Paragraph(
    "The site auto-refreshes every Monday at 06:00 UTC via a GitHub Actions workflow. "
    "The workflow runs <font face='Courier'>scripts/update_data.py</font>, which pulls the latest "
    "values from each adapter, appends a new row per region per KPI to <font face='Courier'>data/historical.csv</font>, "
    "writes a frozen JSON snapshot to <font face='Courier'>data/snapshots/YYYY-Wxx.json</font>, "
    "and overwrites <font face='Courier'>data/current.json</font>. Netlify auto-deploys on the resulting commit.",
    body))

story.append(Paragraph("7.2 Open data", h2))
story.append(Paragraph(
    "Every value the dashboard has ever shown is downloadable as a single CSV (historical.csv) "
    "or as individual weekly JSON snapshots. Snapshots are never edited after the fact &mdash; "
    "if a source revises a figure, the new value enters a future snapshot, not the past one. "
    "This makes the data store an audit trail as much as a source.",
    body))

# ----- 8. Limitations and caveats -----
story.append(Paragraph("8. Limitations and caveats", h1))

story.append(Paragraph("8.1 AI washing", h2))
story.append(Paragraph(
    "Layoffs.fyi indicates roughly 48% of 2026 tech layoffs are \"AI attributed\" by the employer, "
    "while a stricter count puts the genuine-automation figure closer to 20%. The Hill and Crunchbase "
    "both quote analysts arguing that AI announcements are partly a cover for reallocating budgets "
    "to AI infrastructure, not for net headcount reduction caused by automation. Every AI-attributed "
    "layoff event in this tracker carries an attribution-confidence score (1 to 5) so reports can be "
    "filtered by stringency.",
    body))

story.append(Paragraph("8.2 Survey lag and sampling", h2))
story.append(Paragraph(
    "Anthropic Economic Index releases are quarterly and based on a one-week sample window. "
    "BLS, ONS, NSO, and Eurostat LFS data publish with a one to three month lag. The dashboard "
    "surfaces the freshness timestamp on every tile so users know what is live and what is structural.",
    body))

story.append(Paragraph("8.3 Country-brief comparability", h2))
story.append(Paragraph(
    "Anthropic country briefs measure usage by Claude users in that country, not the country's "
    "workforce. Cross-country absolute comparisons of Observed Exposure are misleading. The "
    "within-country quartile rank is the only safe comparable.",
    body))

story.append(Paragraph("8.4 Scraping legality", h2))
story.append(Paragraph(
    "LinkedIn's terms prohibit unauthorised scraping; only the licensable LinkedIn Economic Graph "
    "feed is used. Indeed Hiring Lab, Seek Employment Trends, Naukri JobSpeak, and equivalent "
    "aggregators provide ToS-compliant aggregated feeds. The pipeline never stores raw job postings; "
    "it stores aggregated metrics only.",
    body))

story.append(Paragraph("8.5 Causal modesty", h2))
story.append(Paragraph(
    "Even with the best current measures, the differential unemployment signal in the US is "
    "statistically indistinguishable from zero. This tool is built to detect movement as it emerges, "
    "not to assert causation prematurely. Every monthly and yearly report includes a section on "
    "alternative explanations &mdash; trade, policy, business cycle, demographic shift &mdash; "
    "that could account for the same observation.",
    body))

# ----- 9. References -----
story.append(Paragraph("9. References", h1))
refs = [
    'Massenkoff, M. and McCrory, P. (2026). <i>Labor market impacts of AI: A new measure and early evidence.</i> Anthropic, 5 March 2026. https://www.anthropic.com/research/labor-market-impacts',
    'Anthropic (2026). <i>Anthropic Economic Index: Learning curves.</i> March 2026.',
    'Anthropic (2026). <i>Anthropic Economic Index: Economic primitives.</i> January 2026.',
    'Anthropic (2026). <i>India country brief, Anthropic Economic Index.</i>',
    'Anthropic (2026). <i>How Australia uses Claude.</i>',
    'Anthropic dataset, Anthropic/EconomicIndex on Hugging Face. https://huggingface.co/datasets/Anthropic/EconomicIndex',
    'Eloundou, T., Manning, S., Mishkin, P., and Rock, D. (2023). <i>GPTs are GPTs: An early look at the labor market impact potential of large language models.</i> arXiv 2303.10130.',
    'Brynjolfsson, E., Chandar, B., and Chen, R. (2025). <i>Canaries in the coal mine? Six facts about the recent employment effects of artificial intelligence.</i> Digital Economy.',
    'World Economic Forum (2025). <i>Future of Jobs Report 2025.</i>',
    'UK Government (2025). <i>Assessment of AI capabilities and the impact on the UK labour market.</i>',
    'Bank of England (2026). <i>Generative AI: degenerative for jobs?</i> Bank Underground, 22 January 2026.',
    'Nasscom (2026). <i>India\'s workforce transformation opportunity in the AI era.</i>',
    'European Commission. <i>Apply AI Strategy and Union of Skills programme.</i>',
    'Indeed Hiring Lab Australia (2026). <i>Nothing artificial about Australian AI adoption.</i>',
    'Layoffs.fyi tech and startup layoff tracker.',
    'CNBC (2026). <i>20,000 job cuts at Meta, Microsoft raise concern that AI-driven labor crisis is here.</i>',
]
for r in refs:
    story.append(Paragraph('<font color="#FF5C39">&bull;</font>&nbsp; ' + r,
        ParagraphStyle("ref", parent=small, leftIndent=12, spaceAfter=4)))

story.append(Spacer(1, 1*cm))
story.append(Paragraph(
    "<i>Prepared June 2026 &mdash; v1.0. Updates to this manual will follow major methodological revisions.</i>",
    small))

# ------------------------------------------------------------------
# BUILD
# ------------------------------------------------------------------
doc = SimpleDocTemplate(
    str(OUT),
    pagesize=A4,
    title="AI Job Market Impact Tracker - User Manual",
    author="AWA (Advanced Workplace Associates)",
    leftMargin=1.8*cm, rightMargin=1.8*cm,
    topMargin=2.0*cm, bottomMargin=1.8*cm,
)
doc.build(story, onFirstPage=on_cover, onLaterPages=on_page)
print(f"Wrote {OUT}  ({OUT.stat().st_size} bytes)")
