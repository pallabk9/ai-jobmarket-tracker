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

# ---- Brand fonts: Manrope + Spectral (AWA Brand book), with graceful fallback ----
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
_FONTS = ROOT / "assets" / "fonts"
try:
    pdfmetrics.registerFont(TTFont("Spectral", str(_FONTS / "Spectral-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Spectral-Bold", str(_FONTS / "Spectral-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Spectral-Italic", str(_FONTS / "Spectral-Italic.ttf")))
    pdfmetrics.registerFont(TTFont("Manrope", str(_FONTS / "Manrope-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Manrope-Bold", str(_FONTS / "Manrope-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Manrope-SemiBold", str(_FONTS / "Manrope-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont("Manrope-ExtraBold", str(_FONTS / "Manrope-ExtraBold.ttf")))
    pdfmetrics.registerFontFamily("Spectral", normal="Spectral", bold="Spectral-Bold", italic="Spectral-Italic", boldItalic="Spectral-Bold")
    pdfmetrics.registerFontFamily("Manrope", normal="Manrope", bold="Manrope-Bold", italic="Manrope", boldItalic="Manrope-Bold")
    SERIF, SERIF_B, SERIF_I = "Spectral", "Spectral-Bold", "Spectral-Italic"
    SANS, SANS_B, SANS_SB, SANS_XB = "Manrope", "Manrope-Bold", "Manrope-SemiBold", "Manrope-ExtraBold"
    print("Brand fonts registered: Manrope + Spectral")
except Exception as _fe:
    print("Brand fonts unavailable (%s); using Times/Helvetica fallback" % _fe)
    SERIF, SERIF_B, SERIF_I = "Times-Roman", "Times-Bold", "Times-Italic"
    SANS, SANS_B, SANS_SB, SANS_XB = "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica-Bold"


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
# (font names are defined above with the brand-font registration)

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

# ---------------- AWA LOGO (official master horizontal lockup) ----------------
LOGO_COLOR = ROOT / "assets" / "awa-logo-h.png"        # Midnight wordmark, transparent
LOGO_WHITE = ROOT / "assets" / "awa-logo-h-white.png"  # reversed (white) for dark grounds
_LOGO_ASPECT = 1171.0 / 428.0

def draw_awa_logo(c, x, y, h, dark_bg=False):
    """Place the supplied AWA horizontal lockup PNG.
    x = left edge, y = vertical centre, h = lockup height in points."""
    w = h * _LOGO_ASPECT
    path = LOGO_WHITE if dark_bg else LOGO_COLOR
    try:
        c.drawImage(str(path), x, y - h / 2.0, width=w, height=h,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass

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
    draw_awa_logo(c, M, H - 2.15 * cm, 24, dark_bg=True)
    c.setFont(SANS, 8.5); c.setFillColor(DARKMUTE)
    c.drawRightString(W - 1.5 * cm, H - 2.02 * cm, "USER MANUAL     v3.0     AUGUST 2026")
    # kicker (Spectral italic, coral)
    c.setFont(SERIF_I, 16); c.setFillColor(CORAL)
    c.drawString(M, H * 0.63, "The DNA of work")
    # title (Spectral bold, white)
    c.setFillColor(WHITE); c.setFont(SERIF_B, 35)
    c.drawString(M, H * 0.63 - 1.2 * cm, "AI Job Market")
    c.drawString(M, H * 0.63 - 2.4 * cm, "Impact Tracker")
    # subtitle
    c.setFont(SANS, 15); c.setFillColor(LIGHT)
    c.drawString(M, H * 0.63 - 3.5 * cm, "User manual")
    c.setStrokeColor(CORAL); c.setLineWidth(1.4)
    c.line(M, H * 0.63 - 3.95 * cm, M + 4.6 * cm, H * 0.63 - 3.95 * cm)
    # description
    c.setFont(SANS, 10.5); c.setFillColor(DARKMUTE)
    desc = ["How the dashboard works, what every term means,",
            "and where every number comes from.",
            "Grounded in the Anthropic Observed Exposure methodology.",
            "Six regions  -  weekly refresh."]
    yy = H * 0.63 - 4.8 * cm
    for ln in desc:
        c.drawString(M, yy, ln); yy -= 0.55 * cm
    # byline
    c.setFillColor(WHITE); c.setFont(SANS_B, 13)
    c.drawString(M, 3.3 * cm, "Developed by AWA")
    c.setFillColor(DARKMUTE); c.setFont(SANS, 9.5)
    c.drawString(M, 3.3 * cm - 0.52 * cm, "Advanced Workplace Associates     Research instrument")
    # baseline rule + footer
    c.setStrokeColor(colors.HexColor("#33485A")); c.setLineWidth(0.8)
    c.line(M, 2.15 * cm, W - M, 2.15 * cm)
    c.setFillColor(DARKMUTE); c.setFont(SANS, 8)
    c.drawString(M, 1.65 * cm, "Version 3.0  -  August 2026")
    c.drawRightString(W - M, 1.65 * cm, "It's in our DNA")
    c.restoreState()

def on_page(canvas, doc):
    c = canvas
    W, H = A4
    M = 1.8 * cm
    c.saveState()
    # header: small logo left, running title right, hairline under
    draw_awa_logo(c, M, H - 1.15 * cm, 13, dark_bg=False)
    c.setFont(SANS, 8); c.setFillColor(MUTED)
    c.drawRightString(W - M, H - 1.2 * cm, "AI Job Market Impact Tracker     User manual")
    c.setStrokeColor(LIGHT); c.setLineWidth(0.8)
    c.line(M, H - 1.5 * cm, W - M, H - 1.5 * cm)
    # footer: byline left, tagline centre, page right, hairline above
    c.line(M, 1.4 * cm, W - M, 1.4 * cm)
    c.setFont(SANS, 8); c.setFillColor(MUTED)
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
    "The dashboard opens in a <b>Simple</b> view built for a fast, plain-language read: one "
    "Job Impact Index per region, five plain-language composite indexes (three risk indexes "
    "plus two positive-direction creation indexes that pull the composite down), and a sector "
    "pulse ranking eleven industry sectors by AI pressure. A <b>Deep</b> toggle exposes "
    "everything underneath &mdash; the ten raw KPIs with measured/modelled provenance, the "
    "analytical charts, and \"under the hood\" lineage panels that show every input, "
    "calibration band and weight behind every derived number. A data-provenance narrative at "
    "the top of the page states the sourcing contract: measured values come from authoritative "
    "primary sources; where none exists, reliable, fully cited models grounded in peer-reviewed "
    "and institutional research stand in, always labelled. Sections 5.1 and 5.2 explain both "
    "layers in detail.",
    body))
story.append(Paragraph(
    "<b>Terminology (August 2026 review).</b> For a corporate-leadership audience the dashboard "
    "now uses <b>AI Footprint</b> as its plain-language term for the formal research construct "
    "<i>Observed Exposure</i> (the research term is retained in citations and formulas), and "
    "<b>Untapped AI Potential</b> for what was previously labelled the <i>capability gap</i> "
    "&mdash; what AI could theoretically do minus what it is observed doing.",
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
    ("Untapped AI Potential (formerly capability gap)",
     "Theoretical &beta; (Eloundou) minus AI Footprint (Observed Exposure), averaged across the region's occupations weighted by current employment. Expressed in percentage points &mdash; the headroom AI has not yet converted into practice.",
     "Eloundou et al. 2023 plus Anthropic Economic Index.",
     "Monthly.",
     "Potential converts (gap closes) by more than 3 pp."),
    ("Augmentation share",
     "Percentage of Claude conversations in the region's traffic mix classified as collaborative (augmentative) rather than end-to-end (automated).",
     "Anthropic Economic Index quarterly release.",
     "Quarterly.",
     "Below 45% or above 60%."),
    ("Exposed-occupation posting index",
     "Mean Indeed postings index across eight high-exposure sectors, seasonally adjusted, indexed to February 2020 = 100. Measured for the US, UK, EU (DE+FR mean) and AU; India and APAC use Adzuna exposed-category counts (indexed to their first measured week) once the API key is configured.",
     "Indeed Hiring Lab job postings tracker (open GitHub dataset); Adzuna categories for India/APAC.",
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
     "New AI, ML, data, security postings minus AI-attributed displacement events over the latest 12 months, in thousands of roles. Since Aug 2026 a Deep-view context KPI (it powers the Net job change chart); the AI Job Creation Index now runs on the advertised-AI-jobs count below.",
     "WEF Future of Jobs 2025 regional baseline plus posting-derived adjustments.",
     "Quarterly.",
     "Net swings into negative territory."),
    ("Advertised AI-skill jobs (live ads)",
     "Count of live job ads matching the AI term set (ai, genai, llm, chatgpt, copilot, tensorflow, pytorch), in thousands, summed across the region's Adzuna markets (EU = DE+FR; APAC = Singapore proxy). A keyword net: an ad mentioning AI counts whether AI is the whole job or one skill among many. Powers the AI Job Creation Index, scored as an index against its launch baseline (=100).",
     "Adzuna live job-ad counts (measured, all six regions).",
     "Weekly.",
     "Index vs launch baseline falls below 80."),
    ("Employment in new AI businesses",
     "Estimated people employed at AI-first businesses founded in the last three years, in thousands. Modelled: Stanford AI Index newly-funded AI startup counts per geography x a three-year founding cohort x ~15 average early-stage headcount; unfunded formations conservatively excluded. No statistics agency measures this directly. Powers the AI New Enterprise Index.",
     "AWA model; anchors from the Stanford AI Index and OECD.AI.",
     "Revisited with each anchor publication (at least annually).",
     "Anchor revision moves a region by more than 25%."),
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

story.append(Paragraph("5.1 Simple and Deep views &mdash; the derived layer (added Aug 2026; five-index Job Impact composite, Aug 2026 review)", h2))
story.append(Paragraph(
    "The dashboard opens in <b>Simple</b> view: one <b>Job Impact Index</b> (0&ndash;100) per region "
    "&mdash; how AI is increasing or reducing the number of jobs available in the areas of work where "
    "AI can most readily be applied &mdash; built from five plain-language indexes, each carrying a "
    "fixed \"Measures &hellip;\" definition and a direction line (\"the higher the number &hellip;\") "
    "on its tile. Three are risk indexes that push the composite up: the <i>AI Redundancy Index</i> "
    "(reported redundancies attributed to AI displacement, counted where the source tracks AI "
    "attribution &mdash; the UK series counts all redundancies; the score is grounded in the current "
    "volume of cutting against fixed bands, and the tile always prints the absolute figure), the "
    "<i>AI Advertised Job Displacement Index</i> (the reduction in advertised jobs in the occupations "
    "most exposed to AI versus what would have been expected before AI &mdash; posting level and "
    "12-week trend), and the <i>Graduate Unemployment Index</i> (graduate and young-worker "
    "unemployment versus the historically expected norm). Two are <b>positive-direction</b> creation "
    "indexes that enter the composite inverted and pull it <b>down</b>: the <i>AI Job Creation "
    "Index</i> (the number of newly advertised jobs that call for AI &mdash; the measured Adzuna count "
    "of live ads matching AI terms, indexed to its launch baseline) and the <i>AI New Enterprise "
    "Index</i> (people employed in new businesses created because of AI &mdash; a clearly badged "
    "modelled estimate anchored to published AI-startup formation data, since no statistics agency "
    "measures this directly). Composite weights: 25% Redundancy + 25% Advertised Displacement + 20% "
    "Graduate Unemployment + 15% &times; (100 &minus; Job Creation) + 15% &times; (100 &minus; New "
    "Enterprise). The two creation indexes overlap only slightly &mdash; an advertised role at a newly "
    "founded AI firm can appear in both &mdash; a documented design choice, since they track different "
    "mechanisms (incumbents advertising AI roles vs AI spawning new businesses) and together cap at "
    "30% of the composite. An earlier <i>AI Adoption Index</i> was retired in August 2026: AI arriving "
    "in work is a leading indicator rather than a job outcome; its underlying signals remain visible "
    "as raw KPI tiles in Deep view.", body))
story.append(Paragraph(
    "The Graduate Unemployment Index carries an explicit caveat on its tile: it is an <b>inference "
    "indicator</b> &mdash; it tends to move with AI pressure, but graduate unemployment can also "
    "reflect the wider economic cycle and other causes. Each index scores its input KPIs against "
    "fixed calibration bands (linear 0&ndash;100 between a documented floor and ceiling, clamped). "
    "Status words &mdash; Low (&lt;25), Moderate (25&ndash;50), Elevated (50&ndash;70), High (&ge;70); "
    "the positive-direction creation index instead reads Weak / Moderate / Encouraging / Strong with "
    "an inverted colour scale &mdash; always accompany the colour, and every score carries a "
    "confidence chip: the share of its weight backed by <i>measured</i> (not modelled) sources that "
    "week. Every index tile carries a dynamically generated reading &mdash; how far the index moved "
    "versus last month and versus its recent-months average, which underlying input drove the move "
    "(with its raw values), and the implication &mdash; and the hero panel carries the same kind of "
    "generated narrative for the Job Impact Index itself: its movement versus last month and versus "
    "the recent average, plus the biggest-moving index behind the change. Every mini sparkline "
    "(including the Job Impact Index's own, on the right of the hero panel) is clickable: it opens a "
    "full history chart with the index on the y-axis and the weekly timeline on the x-axis.", body))
story.append(Paragraph(
    "Switching to <b>Deep</b> view reveals everything underneath: the ten raw KPI tiles with their "
    "measured/modelled badges, the full analytical charts, and an \"Under the hood\" panel on every "
    "index card tracing each input's raw value &rarr; calibration band &rarr; normalised score &rarr; "
    "weight &rarr; contribution, with source links (the creation card's lineage also prints the "
    "100&nbsp;&minus;&nbsp;score inversion). The derived layer is computed in the browser from "
    "current.json and historical.csv &mdash; the lineage displayed is the live calculation, so the "
    "dashboard and its documentation cannot drift apart. Bands, weights and the missing-input rule "
    "are specified in DERIVED_METRICS.md in the repository. Two integrity safeguards apply "
    "(added Aug 2026): a <b>regime-break guard</b> - a 12-week-change input is only computed when "
    "both endpoints share the same measured/modelled basis, so a KPI switching from a modelled "
    "placeholder to a measured source can never manufacture a spurious trend (the input's weight "
    "redistributes until the new basis accrues 12 weeks of history) - and <b>basis-aware "
    "calibration</b>: where regions publish the same signal on different bases, each basis scores "
    "against its own fixed band - the AI Redundancy Index scores cumulative YTD layoff series against a "
    "12-week-flow band and the UK's rolling-quarter redundancy level against a level band. "
    "Scores compare a region to itself over "
    "time and are not cross-country footprint rankings, consistent with the quartile-rank rule in "
    "section 8.3.", body))

story.append(Paragraph("5.2 Sector pulse (added Aug 2026; all six regions; eleven sectors)", h2))
story.append(Paragraph(
    "AI impact by sector &mdash; banking &amp; financial markets, insurance, IT &amp; software, telecom "
    "&amp; media, manufacturing, healthcare, retail, professional services, education, government, and "
    "power &amp; utilities (ISIC sections D+E merged; added Aug 2026). "
    "Each sector's <b>AI Footprint index</b> is the employment-share-weighted mean of the locked "
    "Anthropic Observed Exposure scores across that sector's occupation mix (occupation&times;industry "
    "matrices: BLS OEWS for the US; ONS SOC&times;SIC ad-hoc joined to the AWA UK model; Eurostat "
    "ISCO&times;NACE; ILOSTAT ISCO&times;ISIC annual matrices for Australia, India and the APAC "
    "composite, which pools Singapore, Japan and Korea), displayed within-region only with the top "
    "sector indexed at 100. <b>Sector pressure</b> blends the AI Footprint index (45%) with the "
    "posting trend or hiring momentum (25%), official vacancy/employment momentum (15%), and announced "
    "layoffs as a share of the sector's workforce (15%, where published: US via the Challenger "
    "30-industry monthly table, EU via the Eurofound European Restructuring Monitor, trailing 12 "
    "months) on fixed bands. Components a region does not publish have their weight redistributed "
    "pro-rata, and the Deep-view lineage names every input used and every input missing.", body))
story.append(Paragraph(
    "The live-signal cards distinguish <b>online job ads</b> (real-time ads scraped from the web "
    "&mdash; the Indeed sector index or Adzuna counts; fast but unofficial) from <b>official "
    "vacancies</b> (the statistics agency's survey of unfilled positions; slower but authoritative) "
    "&mdash; two different instruments for the same demand question, labelled and explained on the "
    "panel. Signals no source publishes for a region appear as explicit \"not published\" stubs "
    "rather than silently missing. Where a region's statistics only publish industry sections, "
    "sectors sharing a section (e.g. banking and insurance in section K) share an AI Footprint score "
    "and are marked \"section-level\"; power &amp; utilities merges sections D and E before scoring "
    "(UK employment and vacancies sum the ONS D and E series; EU employment sums NACE D+E; Australia "
    "uses ANZSIC division D, which spans both; US layoffs sum Challenger's Energy and Utility rows; "
    "EU layoffs sum the ERM's Electricity and Water/Waste sectors; Indeed and Singapore MOM publish "
    "no utilities category, so those cards show \"not published\"). Weekly signals and quarterly "
    "matrix rebuilds run in CI; every signal carries the measured/modelled badge, and Deep view "
    "exposes the full lineage. Taxonomy concordance: model/sector_concordance.csv in the repository.", body))

story.append(Paragraph("5.3 Panel-by-panel guide (Deep view)", h2))

panels = [
    ("Occupations with the largest AI Footprint (table)",
     "Ten occupations in the selected region with the highest AI Footprint (Observed Exposure) "
     "score. The blue bar is the score itself, 0 to 100%. The red bar is the Untapped AI Potential "
     "&mdash; how much room the score has to grow before reaching the theoretical &beta; ceiling. "
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
     "A 12-week line of the exposed-occupation posting index (February 2020 = 100, seasonally "
     "adjusted). A downward slope of more than 5% over a 4-week rolling window is the alert band."),
    ("Untapped AI Potential by sector",
     "Twin bars per sector: blue is theoretical potential (&beta;), red is the AI Footprint "
     "(Observed Exposure). The space between is the Untapped AI Potential. This is the chart to "
     "watch over months and quarters &mdash; if red moves toward blue in a sector, that sector is "
     "converting potential into deployment."),
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
    ["Tier 3 — Real-time market", "Indeed Hiring Lab (postings + AI tracker), Adzuna API, Naukri JobSpeak, Singapore MOM vacancies.", "Weekly-quarterly", "Postings, AI-mention share, vacancy trends, sector demand."],
    ["Tier 4 — Displacement & event", "Challenger, Gray & Christmas (30-industry job-cut table + AI-cited counts), Eurofound European Restructuring Monitor, Layoffs.fyi context, WEF Future of Jobs.", "Monthly-annual", "Sector layoffs, AI-attributed cuts, narrative, alternative attributions."],
]
story.append(header_table(["Tier", "Sources", "Latency", "Role"], tiers,
    [4.5*cm, 6.5*cm, 2.2*cm, 3.8*cm]))

story.append(Paragraph(
    "<b>Wired live sources (v3, Aug 2026).</b> Measured pairs pull weekly from: Indeed Hiring Lab "
    "(exposed-posting index and AI-mention share; US/UK/EU/AU), Adzuna (India and APAC-Singapore "
    "postings and AI-term share, plus the AI-skill salary premium for all six regions; requires the "
    "free API key configured as a repository secret), BLS/ONS/Eurostat/ABS/ILOSTAT (early-career "
    "unemployment delta, all six regions), Challenger Gray &amp; Christmas (US AI-cited layoffs), "
    "ONS redundancies (UK all-cause proxy), BLS CPS youth employment (US hire-rate proxy), Eurostat "
    "recent-graduate employment (EU graduate proxy), and the Anthropic Economic Index (augmentation "
    "share, all six regions). Proxy-fed tiles are renamed on the dashboard to say exactly what they "
    "measure, and only while the proxy value is live. Where no open machine-readable source exists "
    "anywhere (net job creation; AI-attributed layoffs outside the US), the tile stays honestly "
    "<i>modelled</i>. The full per-KPI review lives in SOURCE_REVIEW_2026-08.md in the repository.",
    body))

story.append(Paragraph("7.1 Refresh cycle", h2))
story.append(Paragraph(
    "The site auto-refreshes every Monday at 06:00 UTC via a GitHub Actions workflow. "
    "It runs <font face='Courier'>scripts/update_data.py</font> (KPI refresh: new rows in "
    "<font face='Courier'>data/historical.csv</font>, a frozen snapshot in "
    "<font face='Courier'>data/snapshots/</font>, a rewritten <font face='Courier'>data/current.json</font>) "
    "followed by <font face='Courier'>scripts/update_sectors.py</font> (sector postings, employment, "
    "vacancies and layoffs into <font face='Courier'>data/sectors.json</font> plus the "
    "<font face='Courier'>data/sector_series.csv</font> archive). Quarterly workflows rebuild the "
    "occupation models and the sector exposure matrices. Netlify auto-deploys on every commit.",
    body))

story.append(Paragraph("7.2 Open data", h2))
story.append(Paragraph(
    "Every value the dashboard has ever shown is downloadable: <font face='Courier'>historical.csv</font> "
    "(all KPIs, all regions, all weeks), the weekly JSON snapshots, <font face='Courier'>current.json</font>, "
    "<font face='Courier'>sectors.json</font> (the sector layer: exposure, signals, provenance), "
    "<font face='Courier'>sector_series.csv</font> (append-only sector signal archive) and "
    "<font face='Courier'>uk_occupations.json</font> (the 412-occupation UK model). Snapshots are never "
    "edited after the fact &mdash; if a source revises a figure, the new value enters a future snapshot, "
    "not the past one. This makes the data store an audit trail as much as a source.",
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

story.append(Paragraph("8.6 Derived layers, proxies and parsed sources", h2))
story.append(Paragraph(
    "The Job Impact Index, its indexes and sector pressure are <b>presentation-layer "
    "derivations</b>: they add no new measurement, only fixed, documented calibration bands and "
    "weights over the underlying series, and their full lineage is visible in Deep view. Several "
    "tiles are honest proxies renamed on the dashboard (UK redundancies for layoffs, US youth "
    "employment for the hire rate, EU recent-graduate employment for graduate postings). Two "
    "sector signals are parsed from published text rather than an API &mdash; the Challenger "
    "industry table (PDF) and Naukri JobSpeak (report copy) &mdash; and are therefore brittle to "
    "format changes; a failed parse carries the previous value forward rather than inventing one. "
    "Sector layoff counts are <b>all-cause</b>, not AI-attributed: attribution exists only at the "
    "headline Challenger AI-cited figure. Where statistics agencies publish only industry "
    "sections, sectors sharing a section (banking and insurance; IT and telecom/media) share an "
    "exposure score, marked \"section-level\" on the dashboard.",
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
    'Challenger, Gray & Christmas. <i>Monthly Job Cut Announcement Report</i> (industry table + AI-cited counts). https://www.challengergray.com/blog/category/job-cuts-report/',
    'Eurofound. <i>European Restructuring Monitor events database.</i> https://apps.eurofound.europa.eu/restructuringevents/',
    'Indeed Hiring Lab. <i>Job postings tracker</i> and <i>AI tracker</i> open datasets. https://github.com/hiring-lab',
    'ILOSTAT. <i>Employment by occupation and economic activity (EMP_TEMP_ECO_OCU); employment by economic activity (EMP_TEMP_SEX_ECO).</i> https://ilostat.ilo.org/',
    'ONS ad-hoc 3136 (2025). <i>Employment by occupation and industry section, UK, 2021-2024.</i>',
    'Felten, E., Raj, M., and Seamans, R. (2021). <i>Occupational, industry, and geographic exposure to artificial intelligence.</i> Strategic Management Journal (industry-aggregation precedent for the sector exposure method).',
    'Adzuna. <i>Developer API.</i> https://developer.adzuna.com/',
    'Naukri JobSpeak. <i>Monthly hiring activity report.</i>',
    'Layoffs.fyi tech and startup layoff tracker.',
    'CNBC (2026). <i>20,000 job cuts at Meta, Microsoft raise concern that AI-driven labor crisis is here.</i>',
]
for r in refs:
    story.append(Paragraph('<font color="#FF5C39">&bull;</font>&nbsp; ' + r,
        ParagraphStyle("ref", parent=small, leftIndent=12, spaceAfter=4)))

story.append(Spacer(1, 1*cm))
story.append(Paragraph(
    "<i>Prepared June 2026; revised 26 August 2026 &mdash; v3.0. This revision implements the August 2026 five-index review: renames (AI Redundancy Index; AI Advertised Job Displacement Index), the AI Job Creation Index redefined onto the measured Adzuna count of advertised AI jobs (indexed to its launch baseline), the new modelled AI New Enterprise Index, weights 25/25/20/&minus;15/&minus;15, the documented creation/enterprise overlap boundary, and a direction line on every tile definition. Earlier revisions: v2.x (August 2026) renamed the composite the Job Impact Index, retired the AI Adoption Index, introduced the level-grounded redundancy scoring, the corporate renaming (AI Footprint; Untapped AI Potential), clickable index-history charts, the data-provenance narrative, and the eleventh sector (power &amp; utilities). Updates to this manual follow major methodological revisions.</i>",
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
