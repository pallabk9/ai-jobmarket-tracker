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
  capability_gap:        "Capability gap (theoretical - observed)",
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
  capability_gap: "Theoretical task exposure minus realised (adoption-adjusted) exposure, employment-weighted. UK is now driven by the AWA task-decomposition model — click the 'Capability gap by sector' chart for all 412 occupations.",
  augmentation_share: "Share of Claude conversations that are collaborative (augmentation) rather than end-to-end (automation). Source: Anthropic Economic Index. Refresh: quarterly.",
  exposed_posting_index: "Mean Indeed postings index (Feb 2020 = 100, seasonally adjusted) across eight high-exposure sectors. Measured US/UK/EU(DE+FR)/AU. Refresh: weekly.",
  ai_skill_premium: "Median advertised salary for AI postings minus comparable non-AI postings (%). Source: Indeed Hiring Lab + Lightcast. Modelled.",
  graduate_posting: "Year-on-year change in entry-level postings in exposed roles; Big-4 graduate disclosures used where available. Source: Indeed + IFOW + employer filings. Modelled.",
  net_creation: "New AI/ML/data/security postings minus AI-attributed displacement over the latest 12 months (000s of roles). Source: WEF Future of Jobs 2025 + regional adapters. Modelled.",
};

// State
let DATA = null;
let region = "US";
let cadence = "monthly";
const charts = {};

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
        { label: "Created (K roles)",   data: created,   backgroundColor: "#2E7D32" },
        { label: "Displaced (K roles)", data: displaced, backgroundColor: "#C62828" },
      ],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
      scales: {
        x: { ticks: { font: { size: 10 } }, grid: { color: "#f0f2f7" } },
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
    data: { labels, datasets: [{ data: values, backgroundColor: ["#BBDEFB","#90CAF9","#42A5F5","#1E88E5","#1565C0","#0D47A1"] }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { font: { size: 11 }, boxWidth: 12 } },
        title:  { display: true,
                  text: `${r.demographics.sex.Female}% F / ${r.demographics.sex.Male}% M`,
                  font: { size: 12, weight: "normal" }, color: "#595959" },
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
            datasets: [{ data: [aug, 100 - aug], backgroundColor: ["#2E75B6", "#1F3864"] }] },
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
            borderColor: "#1F3864", backgroundColor: "rgba(46,117,182,0.12)",
            fill: true, tension: 0.3, pointRadius: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: { ticks: { font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { font: { size: 10 } }, grid: { color: "#f0f2f7" }, min: yMin },
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
        { label: l1, data: rawArr,       backgroundColor: "rgba(46,117,182,0.45)", borderColor: "#2E75B6", borderWidth: 1 },
        { label: l2, data: practicalArr, backgroundColor: "#C62828" },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      onHover: (e, els) => { if (clickable && e.native && e.native.target) e.native.target.style.cursor = els.length ? "pointer" : "default"; },
      onClick: () => { if (clickable) openOccModal(null); },
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 } } },
        title:  { display: !!axisTitle, text: axisTitle, font: { size: 11 }, color: "#5a6478", padding: { bottom: 4 } },
        tooltip: { callbacks: { title: (items) => longLabels[items[0].dataIndex] || items[0].label } },
      },
      scales: {
        x: { ticks: { font: { size: 9 }, maxRotation: 45, minRotation: 45, autoSkip: false }, grid: { display: false } },
        y: { ticks: { font: { size: 10 }, callback: (v) => v + "%" }, grid: { color: "#f0f2f7" }, max: 100,
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
      "Theoretical β (Eloundou)", "Observed exposure", false,
      "Theoretical vs observed exposure by sector (%)");
    return;
  }

  if (hint) hint.textContent =
    `Top 10 most AI-exposed ${DATA.regions[region].label} occupations. Click any bar — or the “View all occupations” button — for the full-screen breakdown.`;

  loadOcc(g.detail).then(() => {
    const top = OCC.occupations.slice().sort((a, b) => b.raw - a.raw).slice(0, 10);
    const long  = top.map((o) => o.title || o.soc);
    const short = top.map((o) => (o.title || o.soc).length > 24 ? (o.title || o.soc).slice(0, 23) + "…" : (o.title || o.soc));
    buildGapChart(short, long,
      top.map((o) => +(o.raw * 100).toFixed(1)),
      top.map((o) => +(o.pi  * 100).toFixed(1)),
      "Raw task exposure (theoretical)", "Practical impact (AI-adjusted)",
      true, "Top 10 most AI-exposed UK occupations — raw vs practical (%)");
  }).catch(() => {
    // fall back to the group-level summary still in current.json
    buildGapChart(g.cats, g.names || g.cats, g.theoretical, g.observed,
      "Raw task exposure", "Practical impact", true,
      "AI exposure by sub-major group (%)");
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
        { label: "Raw task exposure (theoretical)", data: rows.map((o) => +(o.raw * 100).toFixed(1)), backgroundColor: "rgba(46,117,182,0.5)" },
        { label: "Practical impact (AI-adjusted)",   data: rows.map((o) => +(o.pi  * 100).toFixed(1)), backgroundColor: "#C62828" },
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
      `<em>Raw exposure</em> is theoretical task susceptibility; <em>practical impact</em> applies sector adoption discounts. Click a row for its task breakdown.`;
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
  Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif";
  Chart.defaults.color = "#1a1a2e";
}

// Bootstrap
(async function init() {
  try {
    const res = await fetch("data/current.json", { cache: "no-store" });
    if (!res.ok) throw new Error("could not load data/current.json");
    DATA = await res.json();
    if (!DATA.regions[region]) region = "US";
    renderAll();
    renderSnapshots();
  } catch (e) {
    document.querySelector("main").insertAdjacentHTML("afterbegin",
      `<div style="background:#FFEBEE;border-left:3px solid #C62828;padding:14px;border-radius:6px;margin-bottom:18px">
        <strong>Could not load data.</strong> The dashboard expected <code>data/current.json</code> in the same folder as <code>index.html</code>. Error: ${e.message}.
       </div>`);
  }
})();
// end dashboard.js
