/* AI Job Market Impact Tracker — dashboard logic
 *
 * Loads data/current.json on first render. Each user pick of region or
 * cadence rebinds every panel. State persists in localStorage.
 */

const CADENCE_NARRATIVE = {
  weekly:  "Weekly view shows the last seven days alongside the four-week rolling baseline. Feeds the weekly regional digest. Refreshed every Monday.",
  monthly: "Monthly view combines structural and market signals. The same data drives the monthly per-region deep-dive report.",
  yearly:  "Yearly view emphasises stocks, bands, and back-tested watch-list performance. Basis for the annual retrospective and forecast.",
};

const KPI_ORDER = [
  "ai_layoffs_ytd",
  "topq_unemp_delta",
  "hire_rate_22_25",
  "ai_mention_postings",
  "capability_gap",
  "augmentation_share",
  "exposed_posting_index",
  "ai_skill_premium",
  "graduate_posting",
  "net_creation",
];

// Display formatters per KPI
const FMT = {
  ai_layoffs_ytd:        (v) => `${v.toFixed(1)}K`,
  topq_unemp_delta:      (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}pp`,
  hire_rate_22_25:       (v) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`,
  ai_mention_postings:   (v) => `${v.toFixed(1)}%`,
  capability_gap:        (v) => `${v.toFixed(0)}pp`,
  augmentation_share:    (v) => `${v.toFixed(0)}%`,
  exposed_posting_index: (v) => `${v.toFixed(0)}`,
  ai_skill_premium:      (v) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`,
  graduate_posting:      (v) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`,
  net_creation:          (v) => `${v.toFixed(0)}K`,
};

// Short KPI display labels (more user-friendly than the long ones)
const KPI_SHORT = {
  ai_layoffs_ytd:        "AI-attributed layoffs (YTD)",
  topq_unemp_delta:      "Early-career unemployment delta",
  hire_rate_22_25:       "Hire rate, 22-25 y/o",
  ai_mention_postings:   "AI-mention posting share",
  capability_gap:        "Untapped AI Potential (could do − doing)",
  augmentation_share:    "Augmentation share",
  exposed_posting_index: "Exposed-occupation posting index",
  ai_skill_premium:      "AI-skill salary premium",
  graduate_posting:      "Graduate posting (exposed)",
  net_creation:          "Net AI-attributed creation",
};

// Per-metric glossary + methodology, surfaced on hover over each KPI tile
// (replaces the old header Glossary/Methodology popups).
const GLOSS = {
  ai_layoffs_ytd: "Cumulative roles cut since 1 Jan where the employer cited AI. Measured for the US from the Challenger monthly Job Cut report; other regions modelled pending a comparable source. Refresh: monthly.",
  topq_unemp_delta: "Youth minus overall unemployment rate (pp, seasonally adjusted) — a published proxy, since no statistics agency reports unemployment by AI exposure. Measured US/UK/EU/AU via BLS, ONS, Eurostat, ABS. Refresh: monthly.",
  hire_rate_22_25: "Year-on-year change in the monthly job-start rate for 22–25 y/o in exposed occupations. Research-derived from Stanford 'Canaries in the Coal Mine' (ADP payroll, US only); modelled, not a live feed.",
  ai_mention_postings: "Share of job postings whose text mentions AI/ML/GenAI terms. Measured US/UK/EU(DE+FR)/AU from the Indeed Hiring Lab AI Tracker. India/APAC modelled (outside Indeed coverage). Refresh: monthly.",
  capability_gap: "Untapped AI Potential: what AI could theoretically do in this region's work minus what it is observed doing today (pp, employment-weighted). A big number = plenty of headroom left; a closing number = adoption catching up with capability. UK is driven by the AWA task-decomposition model — click the 'Untapped AI Potential' chart for all 412 occupations.",
  augmentation_share: "Share of Claude conversations that are collaborative (augmentation) rather than end-to-end (automation). Source: Anthropic Economic Index. Refresh: quarterly.",
  exposed_posting_index: "Mean Indeed postings index (Feb 2020 = 100, seasonally adjusted) across eight high-exposure sectors. Measured US/UK/EU(DE+FR)/AU. Refresh: weekly.",
  ai_skill_premium: "Median advertised salary for AI postings minus comparable non-AI postings (%). Source: Indeed Hiring Lab + Lightcast. Modelled.",
  graduate_posting: "Year-on-year change in entry-level postings in exposed roles; Big-4 graduate disclosures used where available. Source: Indeed + IFOW + employer filings. Modelled.",
  net_creation: "New AI/ML/data/security postings minus AI-attributed displacement over the latest 12 months (000s of roles). Source: WEF Future of Jobs 2025 + regional adapters. Modelled.",
};

// State
let DATA = null;
let HIST = null;               // parsed historical.csv: {week: {region: {kpi: value}}}
let HIST_WEEKS = [];           // sorted iso weeks
let region = "US";
let cadence = "monthly";
let mode = "simple";           // "simple" | "deep"
const charts = {};

/* ==================================================================
   DERIVED METRICS — AI Pressure Index + four pillar signals
   Spec: DERIVED_METRICS.md (repo root). Computed here, client-side,
   from current.json + historical.csv, so the Deep-mode lineage below
   IS the calculation — dashboard and explanation cannot drift apart.
   ================================================================== */

// Fixed calibration bands: raw value at score 0 (floor) and 100 (ceiling).
// Linear in between, clamped. Bands are absolute + identical across regions;
// scores compare a region to itself over time (methodology lock: no absolute
// cross-country exposure claims).
const BANDS = {
  // Two-sided: −10 (cuts easing sharply) → 0 change scores 25 (pace
  // unchanged) → +30 (sharp acceleration). A momentum gauge: 0 means
  // "easing", NOT "no cuts" — the tile shows the absolute level alongside.
  layoffs_pace:   { lo: -10, hi: 30,  label: "12-week change in layoff/redundancy pace (k roles)" },
  creation_idx:   { lo: -50, hi: 150, label: "Net AI-attributed job creation (k roles)" },
  graduate:       { lo: 10,  hi: -40, label: "Graduate postings YoY (%)" },
  posting_level:  { lo: 110, hi: 60,  label: "Posting index level" },
  posting_trend:  { lo: 10,  hi: -10, label: "Posting index, 12-week change" },
  unemp_delta:    { lo: 0,   hi: 10,  label: "Early-career unemployment delta (pp)" },
  hire_rate:      { lo: 10,  hi: -30, label: "Youth hire/employment change (%)" },
  mention_level:  { lo: 0,   hi: 15,  label: "AI-mention posting share (%)" },
  // Adzuna keyword proxy (IN/APAC) is a deliberately looser net than the
  // Hiring Lab curated taxonomy - it needs its own, wider calibration
  mention_level_adz: { lo: 0, hi: 40, label: "AI-mention share, Adzuna keyword basis (%)" },
  mention_trend:  { lo: -1,  hi: 3,   label: "AI-mention share, 12-week change (pp)" },
  automation:     { lo: 30,  hi: 70,  label: "Automation share of AI use (%)" },
  gap_closing:    { lo: 40,  hi: 10,  label: "Untapped AI Potential (pp; closing = high)" },
};

// The five index pillars. Four risk indexes push the AI Impact Index UP;
// the AI Job Creation Index (positive: true) pulls it DOWN — its score
// enters the composite inverted (100 − score). Each input: source KPI,
// band, weight, and how the raw number is obtained (kind: "level" uses the
// current value; "change12w" uses current minus the value 12 weeks earlier;
// "automation" inverts augmentation).
const PILLARS = [
  {
    id: "displacement", label: "Job Cut Index", icon: "✖",
    question: "Are job cuts accelerating?",
    blurb: "The momentum of job cutting — how the pace of announced layoffs and redundancies compares with 12 weeks ago. Around 25 = pace unchanged; higher = accelerating; towards 0 = easing. A low score means cutting is slowing, not that no jobs are being cut — the line below shows how much cutting is still happening.",
    contextKpi: "ai_layoffs_ytd",
    inputs: [
      { kpi: "ai_layoffs_ytd",   band: "layoffs_pace",  weight: 1.00, kind: "pace12w" },
    ],
  },
  {
    id: "pullback", label: "Job Opportunity Decline Index", icon: "▼",
    question: "Are exposed roles being advertised less?",
    blurb: "Whether openings in AI-exposed occupations are shrinking — the level and 12-week trend of job postings in high-AI-footprint roles. Higher = fewer opportunities.",
    inputs: [
      { kpi: "exposed_posting_index", band: "posting_level", weight: 0.60, kind: "level" },
      { kpi: "exposed_posting_index", band: "posting_trend", weight: 0.40, kind: "change12w" },
    ],
  },
  {
    id: "earlycareer", label: "Graduate Unemployment Index", icon: "◎",
    question: "Are young workers feeling it first?",
    blurb: "How early-career workers are faring: the youth-vs-overall unemployment gap, youth hiring, and recent-graduate outcomes.",
    caveat: "An inference indicator — it tends to move with AI pressure, but graduate unemployment can also reflect the wider economic cycle and other causes.",
    inputs: [
      { kpi: "topq_unemp_delta", band: "unemp_delta", weight: 0.50, kind: "level" },
      { kpi: "hire_rate_22_25",  band: "hire_rate",   weight: 0.30, kind: "level" },
      { kpi: "graduate_posting", band: "graduate",    weight: 0.20, kind: "level" },
    ],
  },
  {
    id: "creation", label: "AI Job Creation Index", icon: "✚", positive: true,
    question: "Is AI creating new jobs?",
    blurb: "The positive side of the ledger — net new AI-attributed roles (new AI/ML/data roles minus AI-attributed displacement). A higher score here pulls the AI Impact Index down.",
    inputs: [
      { kpi: "net_creation", band: "creation_idx", weight: 1.00, kind: "level" },
    ],
  },
  {
    id: "adoption", label: "AI Adoption Index", icon: "⚙", wide: true,
    question: "How fast is AI entering work?",
    blurb: "How quickly AI is actually entering work: AI mentions in job ads, the automation share of AI use, and how fast Untapped AI Potential is being converted into practice. Context for the four indexes above — rapid adoption without job creation is what turns footprint into impact.",
    inputs: [
      { kpi: "ai_mention_postings", band: "mention_level", altBand: "mention_level_adz", weight: 0.40, kind: "level" },
      { kpi: "ai_mention_postings", band: "mention_trend", weight: 0.20, kind: "change12w" },
      { kpi: "augmentation_share",  band: "automation",    weight: 0.20, kind: "automation" },
      { kpi: "capability_gap",      band: "gap_closing",   weight: 0.20, kind: "level" },
    ],
  },
];

// Composite weights. The creation pillar enters INVERTED (100 − score):
// strong AI job creation pulls the AI Impact Index down.
const COMPOSITE_WEIGHTS = { displacement: 0.25, pullback: 0.25,
                            earlycareer: 0.20, adoption: 0.15, creation: 0.15 };

const STATUS_BANDS = [
  { max: 25,  word: "Low",      cls: "st-low" },
  { max: 50,  word: "Moderate", cls: "st-mod" },
  { max: 70,  word: "Elevated", cls: "st-elev" },
  { max: 101, word: "High",     cls: "st-high" },
];
const statusOf = (score) => STATUS_BANDS.find((b) => score < b.max);

// Positive-direction pillars (AI Job Creation): high = good, so the status
// words differ and the colour scale is inverted (high score = green).
const POSITIVE_WORDS = [
  { max: 25,  word: "Weak" },
  { max: 50,  word: "Moderate" },
  { max: 70,  word: "Encouraging" },
  { max: 101, word: "Strong" },
];
const statusOfPositive = (score) => ({
  word: POSITIVE_WORDS.find((b) => score < b.max).word,
  cls: statusOf(100 - score).cls,
});
const pillarStatus = (p) =>
  p.positive ? statusOfPositive(p.score || 0) : statusOf(p.score || 0);

function normBand(bandId, raw) {
  const b = BANDS[bandId];
  const t = (raw - b.lo) / (b.hi - b.lo);
  return Math.max(0, Math.min(100, 100 * t));
}

// --- historical.csv loader (tiny CSV parser, quote-aware) ---------
function parseCsv(text) {
  const rows = [];
  let row = [], field = "", inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') inQ = false;
      else field += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (field !== "" || row.length) { row.push(field); rows.push(row); row = []; field = ""; }
      if (c === "\r" && text[i + 1] === "\n") i++;
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows;
}

async function loadHistory() {
  const res = await fetch("data/historical.csv", { cache: "no-store" });
  if (!res.ok) throw new Error("historical.csv unavailable");
  const rows = parseCsv(await res.text());
  const head = rows[0];
  const ix = Object.fromEntries(head.map((h, i) => [h, i]));
  HIST = {};
  for (const r of rows.slice(1)) {
    if (r.length < head.length) continue;
    const wk = r[ix.iso_week], rc = r[ix.region_code], kpi = r[ix.kpi_id];
    const v = parseFloat(r[ix.value]);
    if (!wk || !rc || !kpi || !isFinite(v)) continue;
    // keep the measurement flag: trend inputs must not difference across
    // a modelled->measured basis switch (regime break)
    ((HIST[wk] = HIST[wk] || {})[rc] = HIST[wk][rc] || {})[kpi] =
      { v, m: r[ix.measurement] || "" };
  }
  HIST_WEEKS = Object.keys(HIST).sort();
}

function histValue(week, reg, kpi) {
  const w = HIST[week];
  const node = w && w[reg] ? w[reg][kpi] : undefined;
  return node ? node.v : undefined;
}

function histMeas(week, reg, kpi) {
  const w = HIST[week];
  const node = w && w[reg] ? w[reg][kpi] : undefined;
  return node ? node.m : undefined;
}

// Raw input value for one pillar input as of a given week index in HIST_WEEKS.
// For the newest week, the live current.json value wins over the CSV.
function rawInput(inp, reg, weekIdx) {
  const week = HIST_WEEKS[weekIdx];
  const live = weekIdx === HIST_WEEKS.length - 1
    ? (DATA.regions[reg].kpis[inp.kpi] || {}).value : undefined;
  const now = live !== undefined && live !== null ? live : histValue(week, reg, inp.kpi);
  if (now === undefined) return undefined;
  if (inp.kind === "automation") return 100 - now;
  if (inp.kind === "pace12w") {
    // Change in the PACE of job cutting, per 12 weeks - consistent across
    // the two series bases:
    //  * level series (UK redundancy level - name without "YTD"): the level
    //    IS the pace, so pace change = first difference;
    //  * cumulative YTD series (US Challenger + modelled regions): first
    //    difference is the pace itself (always >= 0), so pace change =
    //    second difference (recent 12-wk pace minus the prior 12-wk pace).
    // Windows are rate-scaled to 12 weeks; each endpoint walks forward to
    // the first week on the SAME measurement basis (regime-break safe).
    const curNode = DATA.regions[reg].kpis[inp.kpi] || {};
    const mNow = live !== undefined && live !== null
      ? (curNode.measurement || "")
      : (histMeas(week, reg, inp.kpi) || "");
    const walk = (from, upto) => {
      for (let i = from; i <= upto; i++) {
        if ((histMeas(HIST_WEEKS[i], reg, inp.kpi) || "") === mNow
            && histValue(HIST_WEEKS[i], reg, inp.kpi) !== undefined) return i;
      }
      return -1;
    };
    const iPrev = walk(Math.max(0, weekIdx - 12), weekIdx - 1);
    if (iPrev < 0) return undefined;
    const prev = histValue(HIST_WEEKS[iPrev], reg, inp.kpi);
    const paceNow = (now - prev) / (weekIdx - iPrev) * 12;
    const cumulative = /ytd/i.test(curNode.name || "");
    if (!cumulative) return paceNow;
    const iPrev2 = walk(Math.max(0, weekIdx - 24), iPrev - 1);
    if (iPrev2 < 0) return undefined;
    const prev2 = histValue(HIST_WEEKS[iPrev2], reg, inp.kpi);
    const pacePrior = (prev - prev2) / (iPrev - iPrev2) * 12;
    return paceNow - pacePrior;
  }
  if (inp.kind === "change12w") {
    const prevWeek = HIST_WEEKS[Math.max(0, weekIdx - 12)];
    const prev = histValue(prevWeek, reg, inp.kpi);
    if (prev === undefined) return undefined;
    // Regime-break guard: never difference a measured value against a
    // modelled baseline (or vice versa) - a basis switch inside the
    // window produces a spurious "trend". The input is treated as not
    // available and its weight redistributes until 12 weeks of the new
    // basis accrue.
    const mNow = live !== undefined && live !== null
      ? ((DATA.regions[reg].kpis[inp.kpi] || {}).measurement || "")
      : (histMeas(week, reg, inp.kpi) || "");
    const mPrev = histMeas(prevWeek, reg, inp.kpi) || "";
    if (mNow && mPrev && mNow !== mPrev) return undefined;
    return now - prev;
  }
  return now;
}

// Score one pillar for (region, week index). Missing inputs redistribute
// their weight pro-rata (per spec). Returns {score, inputs:[...]}.
function scorePillar(pillar, reg, weekIdx) {
  const inputs = pillar.inputs.map((inp) => {
    const raw = rawInput(inp, reg, weekIdx);
    // basis-aware band: the Adzuna keyword proxy uses its own calibration
    const src = ((DATA.regions[reg].kpis[inp.kpi] || {}).source || "");
    const band = inp.altBand && src.includes("Adzuna") ? inp.altBand : inp.band;
    return { ...inp, band, raw, norm: raw === undefined ? undefined : normBand(band, raw) };
  });
  const avail = inputs.filter((i) => i.norm !== undefined);
  if (!avail.length) return { score: undefined, inputs };
  const wSum = avail.reduce((s, i) => s + i.weight, 0);
  const score = avail.reduce((s, i) => s + i.norm * (i.weight / wSum), 0);
  inputs.forEach((i) => {
    i.effWeight = i.norm === undefined ? 0 : i.weight / wSum;
    i.contribution = i.norm === undefined ? 0 : i.norm * i.effWeight;
  });
  return { score, inputs };
}

// Full derived bundle for the selected region at the latest week,
// plus per-pillar + composite history for sparklines and deltas.
function computeDerived(reg) {
  const lastIdx = HIST_WEEKS.length - 1;
  const pillars = PILLARS.map((p) => {
    const now = scorePillar(p, reg, lastIdx);
    const series = HIST_WEEKS.map((_, i) => scorePillar(p, reg, i).score);
    const prevIdx = Math.max(0, lastIdx - 4);
    const delta = (now.score !== undefined && series[prevIdx] !== undefined)
      ? now.score - series[prevIdx] : undefined;
    // confidence = share of effective weight backed by measured KPIs
    const kpis = DATA.regions[reg].kpis;
    const conf = now.inputs.reduce((s, i) =>
      s + ((kpis[i.kpi] || {}).measurement === "measured" ? i.effWeight || 0 : 0), 0);
    return { ...p, score: now.score, inputs: now.inputs, series, delta, confidence: conf };
  });
  // Positive pillars (AI Job Creation) enter the composite inverted:
  // strong creation pulls the AI Impact Index down.
  const cScore = (p, s) => (p.positive ? 100 - s : s);
  const availP = pillars.filter((p) => p.score !== undefined);
  const wSum = availP.reduce((s, p) => s + COMPOSITE_WEIGHTS[p.id], 0);
  const composite = availP.reduce((s, p) =>
    s + cScore(p, p.score) * (COMPOSITE_WEIGHTS[p.id] / wSum), 0);
  const compSeries = HIST_WEEKS.map((_, i) => {
    const scored = PILLARS.map((p) => ({ id: p.id, positive: p.positive,
                                         s: scorePillar(p, reg, i).score }))
      .filter((x) => x.s !== undefined);
    const w = scored.reduce((s, x) => s + COMPOSITE_WEIGHTS[x.id], 0);
    return scored.length ? scored.reduce((s, x) =>
      s + cScore(x, x.s) * (COMPOSITE_WEIGHTS[x.id] / w), 0) : undefined;
  });
  const compPrev = compSeries[Math.max(0, lastIdx - 4)];
  const confidence = availP.reduce((s, p) =>
    s + p.confidence * (COMPOSITE_WEIGHTS[p.id] / wSum), 0);
  return { composite, compSeries,
           compDelta: compPrev !== undefined ? composite - compPrev : undefined,
           confidence, pillars };
}

// --- derived renderers --------------------------------------------
function sparkSvg(series, w, h, cls) {
  const pts = series.map((v, i) => [i, v]).filter(([, v]) => v !== undefined);
  if (pts.length < 2) return "";
  const xs = pts.map(([i]) => i), ys = pts.map(([, v]) => v);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const yMin = Math.min(...ys, 0), yMax = Math.max(...ys, 100);
  const px = (i) => ((i - x0) / (x1 - x0 || 1)) * (w - 4) + 2;
  const py = (v) => h - 3 - ((v - yMin) / (yMax - yMin || 1)) * (h - 6);
  const d = pts.map(([i, v], n) => `${n ? "L" : "M"}${px(i).toFixed(1)},${py(v).toFixed(1)}`).join("");
  const [li, lv] = pts[pts.length - 1];
  return `<svg class="spark ${cls || ""}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true">
    <path d="${d}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    <circle cx="${px(li).toFixed(1)}" cy="${py(lv).toFixed(1)}" r="3" fill="currentColor"/></svg>`;
}

const fmtScore = (s) => (s === undefined ? "—" : Math.round(s));
// invert=true flips the good/bad colour classes (positive-direction pillars:
// a rising AI Job Creation score is good news) while keeping the arrow.
const fmtDelta = (d, invert) => d === undefined ? "" :
  `<span class="pd-delta ${d > 1 ? (invert ? "down" : "up") : d < -1 ? (invert ? "up" : "down") : "flat"}">${d > 1 ? "▲" : d < -1 ? "▼" : "▬"} ${Math.abs(d) < 0.5 ? "steady" : (d > 0 ? "+" : "−") + Math.abs(d).toFixed(0) + " vs last month"}</span>`;

function lineageTable(pillar, reg) {
  const kpis = DATA.regions[reg].kpis;
  const rows = pillar.inputs.map((i) => {
    const k = kpis[i.kpi] || {};
    const b = BANDS[i.band];
    const meas = k.measurement === "measured" ? "measured" : "modelled";
    if (i.raw === undefined) {
      return `<tr class="lin-missing"><td>${b.label}</td><td colspan="4">not available — weight redistributed</td>
        <td><span class="meas meas-${meas}">${meas}</span></td></tr>`;
    }
    return `<tr>
      <td>${b.label}<div class="lin-src"><a href="${k.source_url || "#"}" target="_blank" rel="noopener">${k.source || i.kpi}</a></div></td>
      <td class="num">${i.raw.toFixed(1)}</td>
      <td class="num lin-band">${b.lo} → ${b.hi}</td>
      <td class="num">${i.norm.toFixed(0)}</td>
      <td class="num">× ${(i.effWeight * 100).toFixed(0)}% = <b>${i.contribution.toFixed(1)}</b></td>
      <td><span class="meas meas-${meas}">${meas}</span></td>
    </tr>`;
  }).join("");
  return `<table class="lineage">
    <thead><tr><th>Input (source)</th><th class="num">Raw</th><th class="num">Band 0→100</th>
    <th class="num">Score</th><th class="num">Weight × score</th><th>Provenance</th></tr></thead>
    <tbody>${rows}</tbody>
    <tfoot><tr><td colspan="6">Index score = Σ (weight × normalized input) = <b>${fmtScore(pillar.score)}</b>
    &nbsp;·&nbsp; ${Math.round(pillar.confidence * 100)}% of weight from <em>measured</em> sources${
    pillar.positive ? `<br>This is a <em>positive-direction</em> index: it enters the AI Impact Index inverted
    (100 − ${fmtScore(pillar.score)} = ${pillar.score === undefined ? "—" : Math.round(100 - pillar.score)}), so stronger AI job creation pulls the headline index <b>down</b>.` : ""}</td></tr></tfoot>
  </table>`;
}

// Series registry + full-chart popup for the mini sparklines --------
let SPARKS = {};          // key -> {label, series, positive}
let sparkChart = null;    // live Chart.js instance inside the modal

function openSparkModal(key) {
  const item = SPARKS[key];
  const dlg = document.getElementById("spark-modal");
  if (!item || !dlg) return;
  const title = document.getElementById("spark-modal-title");
  const sub = document.getElementById("spark-modal-sub");
  if (title) title.textContent = `${item.label} — ${DATA.regions[region].label}`;
  if (sub) sub.textContent = item.positive
    ? "Weekly history, 0–100. Positive-direction index: higher = more AI-attributed job creation (pulls the AI Impact Index down)."
    : "Weekly history, 0–100 against fixed calibration bands. Higher = more pressure on this job market.";
  if (!dlg.open) dlg.showModal();
  const pts = HIST_WEEKS.map((w, i) => ({ w, v: item.series[i] }))
    .filter((p) => p.v !== undefined);
  const wrap = dlg.querySelector(".spark-chart-wrap");
  if (typeof Chart === "undefined") {
    // CDN unavailable: fall back to a large inline SVG of the same series
    if (wrap) wrap.innerHTML = sparkSvg(item.series, 860, 380, "spark-fallback");
    return;
  }
  if (wrap && !wrap.querySelector("canvas")) {
    wrap.innerHTML = '<canvas id="sparkModalChart"></canvas>';
  }
  if (sparkChart) { sparkChart.destroy(); sparkChart = null; }
  const ctx = document.getElementById("sparkModalChart");
  if (!ctx) return;
  sparkChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: pts.map((p) => p.w),
      datasets: [{
        label: item.label,
        data: pts.map((p) => +p.v.toFixed(1)),
        borderColor: item.positive ? "#2E7D32" : "#FF5C39",
        backgroundColor: item.positive ? "rgba(46,125,50,0.10)" : "rgba(255,92,57,0.10)",
        fill: true, tension: 0.25, pointRadius: 2, pointHitRadius: 8, borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${item.label}: ${c.parsed.y}` } } },
      scales: {
        y: { min: 0, max: 100,
             title: { display: true, text: `${item.label} (0–100)` } },
        x: { title: { display: true, text: "ISO week" },
             ticks: { maxTicksLimit: 12 } },
      },
    },
  });
}

function bindSparkButtons(host) {
  host.querySelectorAll("[data-spark]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.preventDefault();
      openSparkModal(el.dataset.spark);
    }));
}

// Absolute-level context line for momentum pillars (contextKpi): a low
// Job Cut score means "easing", so the tile must still show how much
// cutting is actually happening.
function pillarContext(p, reg) {
  if (!p.contextKpi) return "";
  const k = DATA.regions[reg].kpis[p.contextKpi];
  if (!k || k.value == null) return "";
  const t = (p.inputs || []).find((i) =>
    (i.kind === "pace12w" || i.kind === "change12w") && i.kpi === p.contextKpi);
  const ch = t && t.raw !== undefined ? t.raw : undefined;
  const cum = /ytd/i.test(k.name || "");
  const unit = cum ? "k/12wk vs the prior 12 wk" : "k vs 12 wk ago";
  const word = ch === undefined ? " · <i>pace change not yet computable on this basis</i>" :
    ch > 1 ? ` · <b>accelerating</b> (pace +${ch.toFixed(1)}${unit})` :
    ch < -1 ? ` · <b>easing</b> (pace −${Math.abs(ch).toFixed(1)}${unit})` :
    " · <b>pace unchanged</b>";
  const meas = k.measurement === "measured" ? "measured" : "modelled";
  const disp = FMT[p.contextKpi] ? FMT[p.contextKpi](k.value) : k.value;
  return `<p class="p-context">Latest level: <b>${disp}</b> — ${k.name}${word}
    <span class="meas meas-${meas}">${meas}</span></p>`;
}

function pillarCard(p, reg) {
  const ps = pillarStatus(p);
  return `
  <article class="pillar ${ps.cls} ${p.positive ? "p-positive" : ""} ${p.wide ? "pillar-wide" : ""}">
    <header>
      <span class="p-q">${p.question}</span>
      <span class="p-label">${p.label}</span>
    </header>
    <div class="p-score-row">
      <span class="p-score">${fmtScore(p.score)}</span>
      <span class="p-status">${ps.word}</span>
      <button type="button" class="spark-btn" data-spark="${p.id}"
        title="Click for the full ${p.label} history chart"
        aria-label="Expand ${p.label} history chart">${sparkSvg(p.series, 170, 52, "")}</button>
    </div>
    <p class="p-blurb">${p.blurb || ""}${p.caveat ? ` <em class="p-caveat">${p.caveat}</em>` : ""}</p>
    ${pillarContext(p, reg)}
    <div class="p-meta">${fmtDelta(p.delta, p.positive)}
      <span class="p-conf" title="Share of this signal's weight backed by measured (not modelled) sources">
        ${Math.round(p.confidence * 100)}% measured</span></div>
    <details class="p-lineage deep-only">
      <summary>Under the hood — how this number is built</summary>
      ${lineageTable(p, reg)}
    </details>
  </article>`;
}

function renderDerived() {
  const host = $("derived");
  if (!host || !HIST) return;
  const d = computeDerived(region);
  const st = statusOf(d.composite || 0);
  // "25% Job Cut + 25% Job Opportunity Decline + … − 15% AI Job Creation"
  const compFormula = PILLARS.map((p, i) =>
    `${i ? (p.positive ? " − " : " + ") : (p.positive ? "− " : "")}` +
    `${Math.round(COMPOSITE_WEIGHTS[p.id] * 100)}% ${p.label.replace(/ Index$/, "")}`).join("");

  // register series for the click-to-expand popups
  SPARKS = { composite: { label: "AI Impact Index", series: d.compSeries } };
  d.pillars.forEach((p) => { SPARKS[p.id] = { label: p.label, series: p.series, positive: p.positive }; });

  const gridPillars = d.pillars.filter((p) => !p.wide);
  const widePillars = d.pillars.filter((p) => p.wide);

  host.innerHTML = `
  <div class="derived-hero ${st.cls}">
    <div class="dh-gauge">
      <svg viewBox="0 0 200 120" width="200" height="120" aria-hidden="true">
        <path d="M20 105 A85 85 0 0 1 180 105" fill="none" stroke="var(--light-2)" stroke-width="14" stroke-linecap="round"/>
        <path d="M20 105 A85 85 0 0 1 180 105" fill="none" stroke="currentColor" stroke-width="14" stroke-linecap="round"
              stroke-dasharray="${(267 * (d.composite || 0) / 100).toFixed(0)} 400"/>
      </svg>
      <div class="dh-score">${fmtScore(d.composite)}<span class="dh-outof">/100</span></div>
    </div><!-- gauge svg scales via CSS -->
    <div class="dh-main">
      <div class="dh-kicker">AI Impact Index · ${DATA.regions[region].label}</div>
      <div class="dh-status">${st.word} impact ${fmtDelta(d.compDelta)}</div>
      <p class="dh-read">One number, 0–100, for AI's net impact on this job market right now.
        Four risk indexes push it up; AI job creation pulls it down:
        ${compFormula} (creation inverted). <b>${Math.round(d.confidence * 100)}%</b> of its weight comes from
        <em>measured</em> sources this week.</p>
    </div>
    <div class="dh-sparkcol">
      <button type="button" class="spark-btn dh-spark-btn" data-spark="composite"
        title="Click for the full AI Impact Index history chart"
        aria-label="Expand AI Impact Index history chart">${sparkSvg(d.compSeries, 260, 64, "")}</button>
      <span class="dh-spark-cap">weekly since ${HIST_WEEKS[0] || ""} · click to expand</span>
      <button type="button" class="ghost-btn dh-how deep-only" data-modal="methodology-modal">Full methodology →</button>
    </div>
  </div>

  <div class="pillar-grid">
    ${gridPillars.map((p) => pillarCard(p, region)).join("")}
  </div>
  ${widePillars.map((p) => pillarCard(p, region)).join("")}
  <p class="derived-note deep-only">Derived metrics are computed in your browser from
    <a href="data/current.json">current.json</a> + <a href="data/historical.csv">historical.csv</a>
    using fixed calibration bands — spec in
    <a href="https://github.com/pallabk9/ai-jobmarket-tracker/blob/main/DERIVED_METRICS.md" target="_blank" rel="noopener">DERIVED_METRICS.md</a>.
    Scores compare a region to itself over time; they are not cross-country footprint rankings.</p>`;

  // the "Full methodology" button reuses the modal opener
  host.querySelectorAll("[data-modal]").forEach((el) => el.addEventListener("click", (e) => {
    e.preventDefault();
    const dlg = document.getElementById(el.dataset.modal);
    if (dlg && !dlg.open) dlg.showModal();
  }));
  bindSparkButtons(host);
}

/* ==================================================================
   SECTOR PULSE — AI impact by sector (Phase 1: US, UK, EU, AU)
   Data: data/sectors.json (exposure from build_sector_model.py,
   signals from update_sectors.py). Sector Pressure is computed HERE,
   client-side, with fixed bands — lineage shown in Deep mode.
   ================================================================== */

let SECTORS = null;         // sectors.json payload
let sectorSel = null;       // selected sector id for the detail panel

// Fixed bands for the sector-pressure blend (same philosophy as pillars)
const SEC_BANDS = {
  postings_delta: { lo: 5, hi: -15 },   // 12-week postings change: falling = pressure
  demand_pct:     { lo: 2, hi: -6 },    // vacancies/employment % change vs prior period
  momentum_yoy:   { lo: 20, hi: -15 },  // YoY hiring % (Naukri IN): shrinking = pressure
  layoffs_rate:   { lo: 0, hi: 1.5 },   // announced cuts as % of sector workforce
};
const SEC_WEIGHTS = { exposure: 0.45, postings: 0.25, demand: 0.15, layoffs: 0.15 };

function secNorm(bandId, raw) {
  const b = SEC_BANDS[bandId];
  return Math.max(0, Math.min(100, 100 * (raw - b.lo) / (b.hi - b.lo)));
}

function sectorPressure(node) {
  const parts = [];    // [key, score, weight, detailText]
  const missing = [];  // absent components, for the lineage panel
  if (node.exposure_rel != null)
    parts.push(["AI footprint", node.exposure_rel, SEC_WEIGHTS.exposure,
      `AI Footprint index ${node.exposure_rel} (within-region, top sector = 100)`]);
  else missing.push(["AI footprint", "no occupation-matrix footprint score yet for this region"]);
  const sig = node.signals || {};
  if (sig.postings && sig.postings.delta12w != null)
    parts.push(["postings", secNorm("postings_delta", sig.postings.delta12w),
      SEC_WEIGHTS.postings,
      `postings ${sig.postings.delta12w >= 0 ? "+" : ""}${sig.postings.delta12w} pts / 12wk (band +5 → −15)`]);
  else if (sig.momentum && sig.momentum.value != null)
    // regions without a postings index (IN) use hiring momentum in its slot
    parts.push(["momentum", secNorm("momentum_yoy", sig.momentum.value),
      SEC_WEIGHTS.postings,
      `hiring ${sig.momentum.value >= 0 ? "+" : ""}${sig.momentum.value}% YoY (band +20% → −15%)`]);
  else missing.push(["postings / momentum", "no posting index or hiring-momentum source publishes this sector here"]);
  const demand = sig.vacancies || sig.employment;
  if (demand && demand.delta_prev != null && demand.value) {
    const pct = 100 * demand.delta_prev / Math.max(1e-9, demand.value - demand.delta_prev);
    parts.push(["demand", secNorm("demand_pct", pct), SEC_WEIGHTS.demand,
      `${sig.vacancies ? "vacancies" : "employment"} ${pct >= 0 ? "+" : ""}${pct.toFixed(1)}% vs prior period (band +2% → −6%)`]);
  } else missing.push(["demand momentum", "no vacancy/employment change published yet for this sector"]);
  // layoffs enter the blend only when employment exists to rate them against
  if (sig.layoffs && sig.layoffs.value != null && sig.employment && sig.employment.value) {
    const rate = 100 * sig.layoffs.value / (sig.employment.value * 1000);
    parts.push(["layoffs", secNorm("layoffs_rate", rate), SEC_WEIGHTS.layoffs,
      `${Number(sig.layoffs.value).toLocaleString("en-GB")} ${sig.layoffs.unit} ≈ ${rate.toFixed(2)}% of sector workforce (band 0% → 1.5%)`]);
  } else if (sig.layoffs && sig.layoffs.value != null) {
    missing.push(["layoffs (in blend)", "cuts are shown below but not scored - no employment figure to rate them against"]);
  } else {
    missing.push(["layoffs", "no per-sector layoff source publishes this region (US: Challenger; EU: Eurofound ERM)"]);
  }
  if (!parts.length) return { score: null, parts, missing };
  const wSum = parts.reduce((s, p) => s + p[2], 0);
  const score = parts.reduce((s, p) => s + p[1] * (p[2] / wSum), 0);
  return { score, parts, missing };
}

function sectorList() {
  const reg = SECTORS && SECTORS.regions && SECTORS.regions[region];
  if (!reg || !reg.sectors) return null;
  const tax = SECTORS.taxonomy || [];
  return tax.map((t) => {
    const node = reg.sectors[t.id];
    if (!node) return null;
    const p = sectorPressure(node);
    return { id: t.id, label: node.label || t.label, node, pressure: p };
  }).filter(Boolean);
}

function measuredShare(node) {
  const sigs = Object.values(node.signals || {});
  if (!sigs.length) return null;
  return sigs.filter((s) => s.measurement === "measured").length / sigs.length;
}

function renderSectorDetail(list) {
  const item = list.find((x) => x.id === sectorSel);
  const host = $("sector-detail");
  if (!host) return;
  if (!item) { host.innerHTML = ""; host.hidden = true; return; }
  const { node, pressure } = item;
  const title = node.label || item.label;
  const st = statusOf(pressure.score || 0);
  const sig = node.signals || {};
  const reg = SECTORS.regions[region] || {};
  const gran = (reg.matrix || {}).granularity;

  const occRows = (node.top_occupations || []).map((o) => `
    <div class="sd-occ">
      <span class="sd-occ-name">${o.label}</span>
      <div class="sd-occ-bar"><div style="width:${Math.min(100, o.share * 300)}%"></div></div>
      <span class="sd-occ-meta">${(o.share * 100).toFixed(0)}% of jobs · footprint ${o.exposure}</span>
    </div>`).join("");

  const sigCards = [];
  if (sig.postings) sigCards.push(`
    <div class="sd-sig">
      <div class="sd-sig-label">Online job ads <span class="meas meas-${sig.postings.measurement}">${sig.postings.measurement}</span></div>
      <div class="sd-sig-val">${sig.postings.value}<span class="sd-sig-unit"> idx</span></div>
      <div class="sd-sig-sub">${sig.postings.delta12w >= 0 ? "+" : ""}${sig.postings.delta12w} / 12wk</div>
      ${sparkSvg((sig.postings.series || []).map((p) => p.value), 120, 30, "")}
    </div>`);
  if (sig.employment) sigCards.push(`
    <div class="sd-sig">
      <div class="sd-sig-label">Employment <span class="meas meas-${sig.employment.measurement}">${sig.employment.measurement}</span></div>
      <div class="sd-sig-val">${Number(sig.employment.value).toLocaleString("en-GB")}<span class="sd-sig-unit"> ${sig.employment.unit}</span></div>
      <div class="sd-sig-sub">${sig.employment.delta_prev == null ? "" : (sig.employment.delta_prev >= 0 ? "+" : "") + sig.employment.delta_prev + " vs prior · "}${sig.employment.period}</div>
    </div>`);
  if (sig.vacancies) sigCards.push(`
    <div class="sd-sig">
      <div class="sd-sig-label">Official vacancies <span class="meas meas-${sig.vacancies.measurement}">${sig.vacancies.measurement}</span></div>
      <div class="sd-sig-val">${Number(sig.vacancies.value).toLocaleString("en-GB")}<span class="sd-sig-unit"> ${sig.vacancies.unit.replace("k vacancies", "k")}</span></div>
      <div class="sd-sig-sub">${sig.vacancies.delta_prev == null ? "" : (sig.vacancies.delta_prev >= 0 ? "+" : "") + sig.vacancies.delta_prev + " vs prior · "}${sig.vacancies.period}</div>
    </div>`);
  if (sig.layoffs) sigCards.push(`
    <div class="sd-sig">
      <div class="sd-sig-label">Layoffs / job cuts <span class="meas meas-${sig.layoffs.measurement}">${sig.layoffs.measurement}</span></div>
      <div class="sd-sig-val">${Number(sig.layoffs.value).toLocaleString("en-GB")}<span class="sd-sig-unit"> ${sig.layoffs.unit}</span></div>
      <div class="sd-sig-sub">${sig.layoffs.delta_prev == null ? "" : (sig.layoffs.delta_prev >= 0 ? "+" : "") + Number(sig.layoffs.delta_prev).toLocaleString("en-GB") + " " + (sig.layoffs.delta_label || "vs prior") + " · "}${sig.layoffs.period}</div>
    </div>`);
  if (sig.momentum) sigCards.push(`
    <div class="sd-sig">
      <div class="sd-sig-label">Hiring momentum <span class="meas meas-${sig.momentum.measurement}">${sig.momentum.measurement}</span></div>
      <div class="sd-sig-val">${sig.momentum.value >= 0 ? "+" : ""}${sig.momentum.value}<span class="sd-sig-unit"> ${sig.momentum.unit}</span></div>
      <div class="sd-sig-sub">${sig.momentum.period}</div>
    </div>`);

  const wSum = pressure.parts.reduce((s, q) => s + q[2], 0);
  // explicit stubs for core signals this region does not publish
  const stubs = [];
  if (!sig.postings && !sig.momentum) stubs.push(["Online job ads",
    "no posting index or hiring-momentum source covers this sector here"]);
  if (!sig.vacancies) stubs.push(["Official vacancies",
    "no statistical vacancy survey publishes this sector for this region"]);
  if (!sig.employment) stubs.push(["Employment",
    "sector employment arrives with the region's next statistical release"]);
  if (!sig.layoffs) stubs.push(["Layoffs / job cuts",
    "published for US (Challenger) and EU (Eurofound) only - no per-sector layoff source exists for this region"]);
  const stubCards = stubs.map(([t, why]) => `
    <div class="sd-sig sd-sig-missing" title="${why}">
      <div class="sd-sig-label">${t}</div>
      <div class="sd-sig-none">not published</div>
      <div class="sd-sig-sub">${why}</div>
    </div>`).join("");

  const lineageRows = pressure.parts.map((p) => `
    <tr><td>${p[0]}</td><td>${p[3]}</td>
        <td class="num">${p[1].toFixed(0)}</td>
        <td class="num">× ${Math.round(100 * p[2] / wSum)}%</td></tr>`).join("")
    + (pressure.missing || []).map((m) => `
    <tr class="lin-missing"><td>${m[0]}</td>
        <td colspan="3">${m[1]} — its weight is redistributed across the inputs above</td></tr>`).join("");

  host.hidden = false;
  host.innerHTML = `
    <div class="sd-hdr ${st.cls}">
      <div>
        <div class="sd-title">${title} <span class="p-status">${st.word} pressure</span></div>
        <div class="sd-sub">AI Footprint index <b>${node.exposure_rel == null ? "—" : node.exposure_rel}</b>
          ${node.exposure_rank ? `· rank ${node.exposure_rank} of ${list.length} in ${DATA.regions[region].label}` : ""}
          ${gran ? `· <span class="sd-gran" title="${gran === "fine" ? "Occupation-level employment matrix" : "Occupation-major-group matrix (coarser)"}">${gran} matrix</span>` : ""}
          ${node.shared_section ? `· <span class="sd-gran" title="This region's statistics combine this sector with others in one industry section; the AI Footprint score is shared">section-level score</span>` : ""}
        </div>
      </div>
      <button type="button" class="modal-close" id="sd-close" aria-label="Close sector detail">&times;</button>
    </div>
    <div class="sd-body">
      <div class="sd-col">
        <h4>Why AI's footprint is large here</h4>
        ${occRows || "<p class='sd-none'>Occupation breakdown arrives with the next quarterly model build.</p>"}
      </div>
      <div class="sd-col">
        <h4>Live signals</h4>
        <p class="sd-sig-note"><b>Online job ads</b> = real-time ads scraped from the web
          (Indeed index / Adzuna counts) — fast but unofficial. <b>Official vacancies</b> =
          the statistics agency's survey of unfilled positions — slower but authoritative.
          Both measure hiring demand from different instruments.</p>
        <div class="sd-sigs">${(sigCards.join("") + stubCards) || "<p class='sd-none'>No live signals yet for this region.</p>"}</div>
      </div>
    </div>
    <details class="p-lineage deep-only">
      <summary>Under the hood — sector pressure & AI Footprint lineage</summary>
      <table class="lineage">
        <thead><tr><th>Input</th><th>Reading</th><th class="num">Score</th><th class="num">Weight</th></tr></thead>
        <tbody>${lineageRows}</tbody>
        <tfoot><tr><td colspan="4">
          Sector pressure = Σ (weight × normalized input) = <b>${pressure.score == null ? "—" : Math.round(pressure.score)}</b>.
          AI Footprint = 100 × employment-share-weighted mean of occupation-level AI footprint
          (${(SECTORS.exposure_source || {}).name || "Anthropic Observed Exposure"}),
          shown as a within-region index (top sector = 100).
          Matrix: ${(reg.matrix || {}).source || "—"}.
        </td></tr></tfoot>
      </table>
    </details>`;
  const closeBtn = host.querySelector("#sd-close");
  if (closeBtn) closeBtn.addEventListener("click", () => {
    sectorSel = null; renderSectors();
  });
}

function renderSectorHeatmap() {
  if (mode !== "deep" || !SECTORS) return "";
  const regs = Object.keys(SECTORS.regions || {}).filter((r) =>
    (SECTORS.regions[r].sectors && Object.values(SECTORS.regions[r].sectors)
      .some((s) => s.exposure_rel != null)));
  if (!regs.length) return "";
  const tax = SECTORS.taxonomy || [];
  // sequential single-hue ramp (light -> dark), per dataviz sequential rule
  const ramp = ["#F4FAFC", "#D5EDF4", "#9ADBE8", "#5FAABF", "#33657C", "#253746"];
  const cell = (v) => {
    if (v == null) return `<td class="hm-na">—</td>`;
    const i = Math.min(ramp.length - 1, Math.floor(v / (100 / ramp.length)));
    const dark = i >= 3;
    return `<td style="background:${ramp[i]};color:${dark ? "#fff" : "var(--midnight)"}">${Math.round(v)}</td>`;
  };
  const rows = tax.map((t) => `
    <tr><th>${t.label}</th>
      ${regs.map((r) => cell(((SECTORS.regions[r].sectors || {})[t.id] || {}).exposure_rel)).join("")}
    </tr>`).join("");
  return `
  <article class="card span-12 deep-only sector-hm">
    <header class="card-hdr"><h3>Sector AI Footprint heatmap — within-region index</h3>
      <details class="src"><summary>Source &amp; method</summary>
        <p>Each cell is the sector's AI Footprint index <em>within its own region</em> (top sector = 100) —
        employment-share-weighted Anthropic Observed Exposure across the sector's occupation mix.
        Values are not comparable across columns (locked methodology: within-country ranks only).</p>
      </details></header>
    <table class="hm"><thead><tr><th></th>${regs.map((r) => `<th>${r}</th>`).join("")}</tr></thead>
      <tbody>${rows}</tbody></table>
  </article>`;
}

function renderSectors() {
  const host = $("sectors");
  if (!host) return;
  const list = sectorList();
  if (!list || !list.length) { host.innerHTML = ""; return; }
  const ranked = list.slice().sort((a, b) =>
    (b.pressure.score ?? -1) - (a.pressure.score ?? -1));
  const chips = ranked.map((x) => {
    const st = statusOf(x.pressure.score || 0);
    const arrow = x.node.signals && x.node.signals.postings
      ? (x.node.signals.postings.delta12w > 1 ? "▲" :
         x.node.signals.postings.delta12w < -1 ? "▼" : "▬") : "";
    const ms = measuredShare(x.node);
    return `<button type="button" class="sec-chip ${st.cls} ${sectorSel === x.id ? "active" : ""}" data-sector="${x.id}"
      title="${x.label}: ${st.word} pressure${ms != null ? ` · ${Math.round(ms * 100)}% of signals measured` : ""}">
      <span class="sec-name">${x.label}</span>
      <span class="sec-meta"><b>${x.pressure.score == null ? "—" : Math.round(x.pressure.score)}</b> ${st.word} <span class="sec-arrow">${arrow}</span></span>
    </button>`;
  }).join("");
  host.innerHTML = `
  <article class="card span-12 sector-card">
    <header class="card-hdr">
      <h3>Sector pulse — AI impact by sector</h3>
      <details class="src"><summary>Source &amp; method</summary>
        <p><strong>What this shows:</strong> the dashboard sectors ranked by <em>sector pressure</em> —
        a fixed-band blend of AI Footprint index (45%), posting trend or hiring momentum (25%),
        vacancy/employment momentum (15%) and announced layoffs as a share of the sector's
        workforce (15%, where published: US via Challenger, EU via Eurofound ERM). When a
        component isn't published for a sector, its weight is redistributed across the available
        ones — the Deep-view lineage lists exactly what was used and what was missing.
        Click a sector for its occupation make-up and live signals.</p>
        <p><strong>Coverage:</strong> all six regions. India's posting slot uses Naukri JobSpeak
        hiring momentum (% YoY, text-parsed from the monthly report); APAC pools SGP+JPN+KOR
        matrices and uses Singapore MOM vacancies as its proxy demand market. AI Footprint scores
        are within-region indexes, not cross-country comparisons.</p>
      </details>
    </header>
    <div class="sector-strip">${chips}</div>
    <div id="sector-detail" class="sector-detail" ${sectorSel ? "" : "hidden"}></div>
  </article>
  ${renderSectorHeatmap()}`;
  host.querySelectorAll("[data-sector]").forEach((el) =>
    el.addEventListener("click", () => {
      sectorSel = sectorSel === el.dataset.sector ? null : el.dataset.sector;
      renderSectors();
    }));
  renderSectorDetail(list);
}

async function loadSectors() {
  try {
    const res = await fetch("data/sectors.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no sectors.json");
    SECTORS = await res.json();
  } catch (e) { SECTORS = null; }
}

// --- mode toggle ---------------------------------------------------
function applyMode() {
  document.body.classList.toggle("mode-simple", mode === "simple");
  document.body.classList.toggle("mode-deep", mode === "deep");
  document.querySelectorAll("[data-mode]").forEach((e) =>
    e.classList.toggle("active", e.dataset.mode === mode));
}

// ---------- DOM helpers ----------
const $ = (id) => document.getElementById(id);
const fmtDate = (iso) => {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric" });
};

// ---------- Renderers ----------
function renderKpis() {
  const r = DATA.regions[region];
  const cards = KPI_ORDER.map((id) => {
    const k = r.kpis[id];
    if (!k) return "";
    const raw = k.value;
    const display = FMT[id] ? FMT[id](raw) : raw;
    const dirClass = k.direction === "up" ? "dir-up" : (k.direction === "down" ? "dir-down" : "");
    const deltaText = id === "ai_layoffs_ytd"   ? `${DATA.iso_week} cumulative`
                    : id === "augmentation_share" ? "Claude.ai mix"
                    : "vs prior cadence";
    const meas = k.measurement === "measured" ? "measured" : "modelled";
    const measTitle = meas === "measured"
      ? "Pulled from the named source's published data"
      : "Synthetic placeholder series - no live source wired for this region yet";
    const tip = (GLOSS[id] || "").replace(/"/g, "&quot;");
    return `
      <div class="kpi ${dirClass}" tabindex="0">
        <div class="label">${KPI_SHORT[id]}
          <span class="meas meas-${meas}" title="${measTitle}">${meas}</span>
          <span class="kpi-i" aria-hidden="true">i</span></div>
        <div class="val">${display}</div>
        <div class="delta neutral">${deltaText}</div>
        <div class="src">Source: <a href="${k.source_url}" target="_blank" rel="noopener">${k.source}</a></div>
        <div class="kpi-tip" role="tooltip">
          <strong>${KPI_SHORT[id]}</strong>
          <span>${tip}</span>
          <span class="kpi-tip-src">Current source: ${k.source}</span>
        </div>
      </div>`;
  }).join("");
  $("kpis").innerHTML = cards;
}

function renderNarrative() {
  const r = DATA.regions[region];
  $("narrative").innerHTML =
    `<strong>${r.label} &mdash; week ending ${fmtDate(DATA.week_ending)}.</strong> ${r.narrative} <em>${CADENCE_NARRATIVE[cadence]}</em>`;
}

function renderOccTable() {
  const r = DATA.regions[region];
  $("occ-table-body").innerHTML = r.occupations.map((o) => `
    <tr>
      <td>${o.name}</td>
      <td><div class="bar-wrap"><div class="bar-fill" style="width:${o.exposure}%"></div></div></td>
      <td class="num">${o.exposure}%</td>
      <td><div class="bar-wrap"><div class="bar-fill gap" style="width:${o.gap}%"></div></div></td>
    </tr>
  `).join("");
}

function destroy(key) { if (charts[key]) { charts[key].destroy(); charts[key] = null; } }

function renderCvd() {
  destroy("cvd");
  const r = DATA.regions[region];
  // Derive a 5x2 chart from kpis. Use net_creation as headline and split into illustrative buckets.
  const created  = [r.kpis.net_creation.value * 0.35, r.kpis.net_creation.value * 0.25,
                    r.kpis.net_creation.value * 0.18, r.kpis.net_creation.value * 0.12, r.kpis.net_creation.value * 0.10];
  const displaced = [-r.kpis.ai_layoffs_ytd.value * 0.31, -r.kpis.ai_layoffs_ytd.value * 0.22,
                     -r.kpis.ai_layoffs_ytd.value * 0.18, -r.kpis.ai_layoffs_ytd.value * 0.16, -r.kpis.ai_layoffs_ytd.value * 0.13];
  const labels = ["AI/ML eng", "Data sci", "AI gov & risk", "Cyber AI", "AI product"];
  const dispLabels = ["Routine ops", "Admin clerks", "Customer svc", "Junior fin", "Designers"];

  charts.cvd = new Chart($("cvdChart").getContext("2d"), {
    type: "bar",
    data: {
      labels: labels.map((l, i) => `${l} ↑ / ${dispLabels[i]} ↓`),
      datasets: [
        { label: "Created (K roles)",   data: created,   backgroundColor: "#52D2BC" },
        { label: "Displaced (K roles)", data: displaced, backgroundColor: "#FF5C39" },
      ],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
      scales: {
        x: { ticks: { font: { size: 10 } }, grid: { color: "#EAEEEF" } },
        y: { ticks: { font: { size: 10 } }, grid: { display: false } },
      },
    },
  });
}

function renderDemo() {
  destroy("demo");
  const r = DATA.regions[region];
  const labels = Object.keys(r.demographics.age);
  const values = labels.map((k) => r.demographics.age[k]);
  charts.demo = new Chart($("demoChart").getContext("2d"), {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: ["#CDEFF4","#9ADBE8","#6FC2D4","#4F9FB4","#3A6E82","#253746"] }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { font: { size: 11 }, boxWidth: 12 } },
        title:  { display: true,
                  text: `${r.demographics.sex.Female}% F / ${r.demographics.sex.Male}% M`,
                  font: { size: 12, weight: "normal" }, color: "#5A6B78" },
      },
    },
  });
}

function renderAug() {
  destroy("aug");
  const r = DATA.regions[region];
  const aug = r.kpis.augmentation_share.value;
  charts.aug = new Chart($("augChart").getContext("2d"), {
    type: "doughnut",
    data: { labels: ["Augmentation", "Automation"],
            datasets: [{ data: [aug, 100 - aug], backgroundColor: ["#52D2BC", "#253746"] }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "right", labels: { font: { size: 11 }, boxWidth: 12 } } },
    },
  });
}

function renderPost() {
  destroy("post");
  const r = DATA.regions[region];
  const labels = r.posting_series.map((p) => p.iso_week.replace("2026-", ""));
  const values = r.posting_series.map((p) => p.value);
  const yMin = Math.floor(Math.min(...values) - 3);
  charts.post = new Chart($("postChart").getContext("2d"), {
    type: "line",
    data: { labels, datasets: [{ label: "Index", data: values,
            borderColor: "#FF5C39", backgroundColor: "rgba(255,92,57,0.10)",
            fill: true, tension: 0.3, pointRadius: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: { ticks: { font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { font: { size: 10 } }, grid: { color: "#EAEEEF" }, min: yMin },
      },
    },
  });
}

function buildGapChart(shortLabels, longLabels, rawArr, practicalArr, l1, l2, clickable, axisTitle) {
  destroy("gap");
  charts.gap = new Chart($("gapChart").getContext("2d"), {
    type: "bar",
    data: {
      labels: shortLabels,
      datasets: [
        { label: l1, data: rawArr,       backgroundColor: "rgba(154,219,232,0.55)", borderColor: "#3E94A8", borderWidth: 1 },
        { label: l2, data: practicalArr, backgroundColor: "#FF5C39" },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: (e, els) => { if (clickable && e.native && e.native.target) e.native.target.style.cursor = els.length ? "pointer" : "default"; },
      onClick: () => { if (clickable) openOccModal(null); },
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 } } },
        title:  { display: !!axisTitle, text: axisTitle, font: { size: 11 }, color: "#5A6B78", padding: { bottom: 4 } },
        tooltip: { callbacks: { title: (items) => longLabels[items[0].dataIndex] || items[0].label } },
      },
      scales: {
        x: { ticks: { font: { size: 9 }, maxRotation: 45, minRotation: 45, autoSkip: false }, grid: { display: false } },
        y: { ticks: { font: { size: 10 }, callback: (v) => v + "%" }, grid: { color: "#EAEEEF" }, max: 100,
             title: { display: true, text: "% of tasks exposed", font: { size: 10 } } },
      },
    },
  });
}

function renderGap() {
  const g = DATA.regions[region].gap_chart;
  const isModel = !!g.detail;                       // UK task-decomposition model
  const hint = $("gap-hint");
  const btn = $("gap-all-btn");
  if (btn) btn.style.display = isModel ? "inline-block" : "none";

  if (!isModel) {
    if (hint) hint.textContent = "";
    buildGapChart(g.cats, g.names || g.cats, g.theoretical, g.observed,
      "Theoretical potential (Eloundou β)", "AI Footprint (observed)", false,
      "Untapped AI Potential by sector — could do vs doing (%)");
    return;
  }

  const label = DATA.regions[region].label;
  if (hint) hint.textContent =
    `Most AI-exposed ${label} occupations. Click any bar — or the “View all occupations” button — for the full-screen breakdown.`;

  loadOcc(g.detail).then(() => {
    const n = OCC.occupations.length;
    if (btn) btn.textContent = `View all ${n} occupations →`;
    const top = OCC.occupations.slice().sort((a, b) => b.raw - a.raw).slice(0, 10);
    const long  = top.map((o) => o.title || o.soc);
    const short = top.map((o) => (o.title || o.soc).length > 24 ? (o.title || o.soc).slice(0, 23) + "…" : (o.title || o.soc));
    const chartTitle = n <= top.length
      ? `${label} — AI Footprint by occupation group (%)`
      : `Top 10 ${label} occupations by AI Footprint (%)`;
    buildGapChart(short, long,
      top.map((o) => +(o.raw * 100).toFixed(1)),
      top.map((o) => +(o.pi  * 100).toFixed(1)),
      "Theoretical potential (raw tasks)", "Practical impact (AI-adjusted)",
      true, chartTitle);
  }).catch(() => {
    // fall back to the group-level summary still in current.json
    buildGapChart(g.cats, g.names || g.cats, g.theoretical, g.observed,
      "Theoretical potential", "Practical impact", true,
      "AI Footprint by sub-major group (%)");
  });
}

// ---------- Occupation detail modal (per-region, model-driven) ----------
let OCC = null;                 // currently-loaded occupation dataset
const OCC_CACHE = {};           // filename -> dataset

function loadOcc(file) {
  if (OCC_CACHE[file]) { OCC = OCC_CACHE[file]; return Promise.resolve(OCC); }
  return fetch("data/" + file, { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error(file + " missing"); return r.json(); })
    .then((j) => { OCC_CACHE[file] = j; OCC = j; return j; });
}

const fmtInt = (n) => (n == null ? "—" : Math.round(n).toLocaleString("en-GB"));
const fmtPct = (n) => (n == null ? "—" : (n * 100).toFixed(1) + "%");
const fmtNum = (n, d = 1) => (n == null ? "—" : n.toFixed(d));

// Full-screen chart of every (filtered) occupation: raw vs practical exposure.
function renderOccChart(rows) {
  if (charts.occ) { charts.occ.destroy(); charts.occ = null; }
  const wrap = $("occ-chart-wrap");
  if (!wrap) return;
  wrap.style.height = Math.max(280, rows.length * 17) + "px";
  charts.occ = new Chart($("occAllChart").getContext("2d"), {
    type: "bar",
    data: {
      labels: rows.map((o) => `${o.soc} ${o.title || ""}`.slice(0, 46)),
      datasets: [
        { label: "Theoretical potential (raw tasks)", data: rows.map((o) => +(o.raw * 100).toFixed(1)), backgroundColor: "rgba(154,219,232,0.6)" },
        { label: "Practical impact (AI-adjusted)",   data: rows.map((o) => +(o.pi  * 100).toFixed(1)), backgroundColor: "#FF5C39" },
      ],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "top", labels: { font: { size: 11 } } } },
      scales: {
        x: { max: 100, ticks: { callback: (v) => v + "%", font: { size: 10 } }, position: "top" },
        y: { ticks: { font: { size: 8 }, autoSkip: false }, grid: { display: false } },
      },
    },
  });
}

function occRows() {
  if (!OCC) return;
  const q = ($("occ-search").value || "").trim().toLowerCase();
  const grp = $("occ-group").value;
  const sort = $("occ-sort").value;
  let rows = OCC.occupations.slice();
  if (grp && grp !== "ALL") rows = rows.filter((o) => o.smg_code === grp);
  if (q) rows = rows.filter((o) => o.soc.includes(q) || (o.title || "").toLowerCase().includes(q));
  rows.sort((a, b) => sort === "soc" ? a.soc.localeCompare(b.soc) : (b[sort] || 0) - (a[sort] || 0));

  const labels = OCC.task_labels || {};
  $("occ-modal-body").innerHTML = rows.map((o) => {
    const tasks = o.tasks || {};
    const tlist = Object.keys(tasks)
      .filter((t) => (tasks[t] || 0) > 0)
      .sort((a, b) => tasks[b] - tasks[a])
      .map((t) => `<li><span>${labels[t] || t}</span><b>${tasks[t]}%</b></li>`).join("");
    return `
      <tr class="occ-row" data-soc="${o.soc}">
        <td>${o.soc}</td>
        <td>${o.title || ""}</td>
        <td class="num">${fmtInt(o.employment)}</td>
        <td class="num">${fmtPct(o.raw)}</td>
        <td class="num">${fmtPct(o.pi)}</td>
        <td class="num">${fmtNum(o.hrs_week)}</td>
        <td class="num">${fmtInt(o.fte)}</td>
        <td class="num">${o.mult == null ? "—" : o.mult.toFixed(1) + "×"}</td>
        <td class="num">${fmtNum(o.combined_hrs)}</td>
      </tr>
      <tr class="occ-detail-row" data-detail="${o.soc}" hidden>
        <td colspan="9">
          <div class="occ-task-head">${o.title || o.soc} — task-time allocation (% of working week) &amp; AI exposure</div>
          <ul class="occ-tasks">${tlist || "<li>No task profile available</li>"}</ul>
        </td>
      </tr>`;
  }).join("");
  $("occ-modal-foot").textContent =
    `${rows.length} of ${OCC.occupations.length} occupations shown · model as-of ${OCC.as_of} · ${OCC.source}`;

  renderOccChart(rows);

  $("occ-modal-body").querySelectorAll(".occ-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const d = $("occ-modal-body").querySelector(`[data-detail="${tr.dataset.soc}"]`);
      if (d) d.hidden = !d.hidden;
    });
  });
}

function openOccModal(groupCode) {
  const reg = DATA.regions[region];
  const file = reg.gap_chart && reg.gap_chart.detail;
  if (!file) return;
  loadOcc(file).then(() => {
    const label = reg.label || region;
    $("occ-title").textContent = `${label} occupations — AI task-decomposition detail`;
    const sel = $("occ-group");
    sel.innerHTML = `<option value="ALL">All groups (${OCC.n_occupations})</option>` +
      OCC.groups.map((g) => `<option value="${g.code}">${g.code} — ${g.name}</option>`).join("");
    sel.value = groupCode || "ALL";
    $("occ-modal-sub").innerHTML =
      `Practical AI impact on ${label} occupations from a task-decomposition model: 18 capability-scored task categories, ` +
      `time-weighted across ${OCC.n_occupations} occupations and national employment. ` +
      `<em>Theoretical potential</em> is raw task susceptibility to AI; <em>practical impact</em> applies sector adoption discounts — the space between is the Untapped AI Potential. Click a row for its task breakdown.`;
    const dlg = $("occ-modal");
    if (dlg && !dlg.open) dlg.showModal();   // open first so the canvas has layout
    occRows();
  }).catch((e) => {
    const dlg = $("occ-modal");
    $("occ-modal-sub").textContent = "Could not load occupation detail: " + e.message;
    if (dlg && !dlg.open) dlg.showModal();
  });
}

function initOccModal() {
  let t = null;
  const sEl = $("occ-search");
  if (sEl) sEl.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { if (OCC) occRows(); }, 220); });
  ["occ-group", "occ-sort"].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("change", () => { if (OCC) occRows(); });
  });
  const allBtn = $("gap-all-btn");
  if (allBtn) allBtn.addEventListener("click", () => openOccModal(null));
  const dlg = $("occ-modal");
  if (!dlg) return;
  dlg.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dlg.close()));
}
initOccModal();

function renderFeed() {
  const r = DATA.regions[region];
  $("feed").innerHTML = r.feed.map((f) => `
    <div class="feed-item">
      <a href="${f.url}" target="_blank" rel="noopener">${f.headline}</a>
      <div class="feed-meta">
        <span>${f.source} &mdash; ${fmtDate(f.date)}</span>
        <span class="badge conf-${f.conf}">Conf ${f.conf}/5</span>
      </div>
    </div>`).join("");
}

// ---------- Snapshot list ----------
async function renderSnapshots() {
  try {
    const r = await fetch("data/snapshots_index.json");
    const idx = await r.json();
    $("snapshot-list").innerHTML = idx.snapshots.map((w) => `
      <div class="snap">
        <a href="data/snapshots/${w}.json" download>${w}</a>
        <span>JSON</span>
      </div>
    `).join("");
    $("status-snapshots").textContent = `${idx.snapshots.length} weeks`;
  } catch (e) {
    $("snapshot-list").textContent = "Could not load snapshot index.";
  }
}

// ---------- Top-level binders ----------
function renderAll() {
  renderDerived();
  renderSectors();
  renderKpis();
  renderNarrative();
  renderOccTable();
  renderCvd();
  renderDemo();
  renderAug();
  renderPost();
  renderGap();
  renderFeed();

  const lastRefresh = fmtDate(DATA.generated_at);
  $("status-last").textContent  = lastRefresh;
  $("status-week").textContent  = DATA.iso_week;
  $("snapshot-meta").innerHTML  = `<span class="live">●</span> Showing ${DATA.iso_week} (${fmtDate(DATA.week_ending)})`;
  $("dl-current-meta").textContent = `${DATA.iso_week} — week ending ${fmtDate(DATA.week_ending)}`;
}

document.querySelectorAll("[data-region]").forEach((el) => {
  el.addEventListener("click", () => {
    document.querySelectorAll("[data-region]").forEach((e) => e.classList.remove("active"));
    el.classList.add("active");
    region = el.dataset.region;
    try { localStorage.setItem("aijmit.region", region); } catch (e) {}
    renderAll();
  });
});
document.querySelectorAll("[data-mode]").forEach((el) => {
  el.addEventListener("click", () => {
    mode = el.dataset.mode === "deep" ? "deep" : "simple";
    try { localStorage.setItem("aijmit.mode", mode); } catch (e) {}
    applyMode();
    // charts in previously-hidden deep cards need a fresh layout pass
    if (mode === "deep" && DATA) renderAll();
  });
});
document.querySelectorAll("[data-cadence]").forEach((el) => {
  el.addEventListener("click", () => {
    document.querySelectorAll("[data-cadence]").forEach((e) => e.classList.remove("active"));
    el.classList.add("active");
    cadence = el.dataset.cadence;
    try { localStorage.setItem("aijmit.cadence", cadence); } catch (e) {}
    renderNarrative();
  });
});

// Restore prefs
try {
  const r = localStorage.getItem("aijmit.region");
  const c = localStorage.getItem("aijmit.cadence");
  const m = localStorage.getItem("aijmit.mode");
  if (m === "deep" || m === "simple") mode = m;
  if (r) {
    region = r;
    document.querySelectorAll("[data-region]").forEach((e) => e.classList.toggle("active", e.dataset.region === r));
  }
  if (c && CADENCE_NARRATIVE[c]) {
    cadence = c;
    document.querySelectorAll("[data-cadence]").forEach((e) => e.classList.toggle("active", e.dataset.cadence === c));
  } else if (c) {
    // stored cadence is no longer valid (e.g. "daily" after we dropped it)
    try { localStorage.removeItem("aijmit.cadence"); } catch (e) {}
  }
} catch (e) {}

// ---------- Modal popups (glossary & methodology) ----------
function initModals() {
  document.querySelectorAll("[data-modal]").forEach((trigger) => {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      const dlg = document.getElementById(trigger.dataset.modal);
      if (dlg && !dlg.open) dlg.showModal();
    });
  });
  document.querySelectorAll("dialog.modal").forEach((dlg) => {
    dlg.querySelectorAll("[data-close]").forEach((btn) =>
      btn.addEventListener("click", () => dlg.close()));
    // click on the backdrop (outside the dialog box) closes it
    dlg.addEventListener("click", (e) => {
      const box = dlg.getBoundingClientRect();
      const inside = e.clientX >= box.left && e.clientX <= box.right &&
                     e.clientY >= box.top  && e.clientY <= box.bottom;
      if (!inside) dlg.close();
    });
  });
  // deep links like /#glossary still work - they open the popup
  const hashMap = { "#glossary": "glossary-modal", "#methodology": "methodology-modal" };
  const fromHash = hashMap[location.hash];
  if (fromHash) {
    const dlg = document.getElementById(fromHash);
    if (dlg) dlg.showModal();
  }
}
initModals();

// Chart.js defaults
if (typeof Chart !== "undefined") {
  Chart.defaults.font.family = "Manrope, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif";
  Chart.defaults.color = "#253746";
}

// Bootstrap
(async function init() {
  try {
    applyMode();
    const res = await fetch("data/current.json", { cache: "no-store" });
    if (!res.ok) throw new Error("could not load data/current.json");
    DATA = await res.json();
    if (!DATA.regions[region]) region = "US";
    try { await loadHistory(); } catch (e) { HIST = null; }  // derived layer degrades gracefully
    await loadSectors();                                     // sector layer optional too
    renderAll();
    renderSnapshots();
  } catch (e) {
    document.querySelector("main").insertAdjacentHTML("afterbegin",
      `<div style="background:#FFE8E2;border-left:3px solid #FF5C39;padding:14px;border-radius:6px;margin-bottom:18px">
        <strong>Could not load data.</strong> The dashboard expected <code>data/current.json</code> in the same folder as <code>index.html</code>. Error: ${e.message}.
       </div>`);
  }
})();

// ---------- Visitor counter ----------
// Counts once per browser session via counterapi.dev (no backend needed).
(function visitorCounter() {
  const el = document.getElementById("visitor-count");
  if (!el) return;
  let cached = null;
  try { cached = sessionStorage.getItem("aijmt_visits"); } catch (e) {}
  if (cached) { el.textContent = Number(cached).toLocaleString("en-GB"); return; }
  fetch("https://api.counterapi.dev/v1/aijmtracker/visits/up")
    .then((r) => r.json())
    .then((j) => {
      if (j && typeof j.count === "number") {
        el.textContent = j.count.toLocaleString("en-GB");
        try { sessionStorage.setItem("aijmt_visits", String(j.count)); } catch (e) {}
      } else {
        el.textContent = "—";
      }
    })
    .catch(() => { el.textContent = "—"; });
})();
// end dashboard.js
