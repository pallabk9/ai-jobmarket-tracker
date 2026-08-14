# Data-source review — every KPI, every region

**Review date:** 2026-08-14 · **Reviewer:** Cowork session for Dr. Pallab Kakoti
**Scope:** all 10 KPIs × 6 regions, current sourcing status as of snapshot 2026-W32, endpoint
health verified live from this review's sandbox, plus the upgrades implemented in this round.

Legend: ✅ measured (live weekly pull) · 🆕 measured after this round's changes ·
🔑 measured once the free Adzuna key is added as a GitHub secret · ⬜ modelled (carried forward).

## Status matrix (after this round)

| KPI | US | UK | IN | EU | APAC | AU |
|---|---|---|---|---|---|---|
| `ai_layoffs_ytd` | ✅ Challenger | 🆕 ONS redundancies (proxy) | ⬜ | ⬜ | ⬜ | ⬜ |
| `topq_unemp_delta` | ✅ BLS | ✅ ONS | ✅ ILOSTAT | ✅ Eurostat | ✅ ILOSTAT | 🆕 ABS (fixed) |
| `hire_rate_22_25` | 🆕 BLS youth-emp (proxy) | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `ai_mention_postings` | ✅ HL ai-tracker | ✅ | 🔑 Adzuna | ✅ | 🔑 Adzuna (SG) | ✅ |
| `capability_gap` | model-owned | model-owned | model-owned | model-owned | model-owned | model-owned |
| `augmentation_share` | ✅ Anthropic EI | ✅ | ✅ | ✅ | ✅ | ✅ |
| `exposed_posting_index` | ✅ Hiring Lab | ✅ | 🔑 Adzuna | ✅ DE+FR | 🔑 Adzuna (SG) | ✅ |
| `ai_skill_premium` | 🔑 Adzuna | 🔑 | 🔑 | 🔑 DE+FR | 🔑 SG | 🔑 |
| `graduate_posting` | ⬜ | ⬜ | ⬜ | 🆕 Eurostat (proxy) | ⬜ | ⬜ |
| `net_creation` | ⬜ WEF-derived | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

Counting measured (region,KPI) pairs: **21 before → 24 now → 33 once the Adzuna key is added**
(of 54 pairs that are weekly-refreshable; `capability_gap` is owned by the quarterly model builds).

## What was implemented this round

1. **AU early-career unemployment delta — fixed.** The adapter had been failing silently in CI
   for weeks (AU showed `modelled` while US/UK/EU were measured). Root cause: the ABS headline
   `LF` dataflow only publishes unemployment rates for AGE=Total; the age-band series live in the
   separate `LF_AGES` dataflow, and the old runtime "key discovery" also picked a wrong SEX code
   from an unrelated codelist. The adapter now fetches total from `LF` and 15-24 from `LF_AGES`
   as two fully-specified slices, verifies every dimension by name, and returned **+6.24pp
   measured** in live testing.
2. **UK layoffs proxy — wired.** ONS LFS redundancy level (series `BEAO`, thousands, all-cause,
   SA) now feeds the UK tile, relabelled *"Redundancies, rolling quarter (all-cause proxy)"* —
   the label only switches when the proxy value is actually measured, so number and name can
   never disagree. No UK source attributes layoffs to AI; this is the honest nearest series.
3. **US hire-rate proxy — wired.** BLS CPS youth (16-24) employment level vs the 2022 annual
   average (`LNS12000036`), relabelled *"Youth employment vs 2022 (proxy)"*. The Stanford/ADP
   "Canaries" 22-25 hire-rate series is research-derived with no machine-readable feed; this is
   the closest open equivalent. (Live test hit the BLS shared-IP daily quota in the sandbox;
   the CI runner with the `BLS_API_KEY` secret is unaffected, and a plausibility guard rejects
   any wrong-series response.)
4. **EU graduate proxy — wired.** Eurostat `edat_lfse_24` (employment rate of recent graduates,
   20-34, 1-3 years out) year-over-year change, relabelled *"Recent-graduate employment rate,
   YoY (proxy)"*. Verified live: +0.3pp (2025 vs 2024).
5. **Adzuna adapter suite — wired, awaiting your key.** Free registration at
   https://developer.adzuna.com → add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` as GitHub Actions
   secrets (repo → Settings → Secrets and variables → Actions). This flips 9 pairs to measured:
   AI-mention share for India + APAC (Singapore proxy market), exposed-posting index for India +
   APAC (indexed to 100 at first measured week, baseline committed to `data/adzuna_state.json`),
   and the AI-skill salary premium for all six regions (AI-keyword vs all-postings advertised
   salary). Without the key every Adzuna adapter no-ops and values carry forward — the cron
   cannot break. **ToS note:** the free tier is formally a validation trial; sustained production
   use should be confirmed with Adzuna or budgeted for their LMI tier.
6. All 23 offline fixture tests pass, including new fixtures for every adapter above.

## Remaining modelled pairs — the honest picture and the upgrade path

**`ai_layoffs_ytd` for IN / EU / APAC / AU.** AI-*attributed* layoff counts only exist for the
US (Challenger). Nearest options: AU — ABS retrenchments (quarterly, SDMX; feasible next round);
EU — Eurofound ERM restructuring events database (browsable, no clean API; medium effort
scraper); IN — Inc42/Longhouse tech-layoff trackers (scrape, ToS-grey); APAC — no authoritative
open source. Recommendation: wire AU retrenchments next; keep the others modelled rather than
shipping a low-integrity scrape.

**`hire_rate_22_25` for UK / EU / AU / IN / APAC.** Youth-employment-level proxies exist in the
already-integrated sources (ONS A05, Eurostat `lfsq_egan`, ABS `LF_AGES` M3/1524, ILOSTAT
annual). Straightforward next round now that the US template exists — roughly one adapter each,
reusing this round's pattern.

**`graduate_posting` for US / UK / IN / AU.** No open "graduate postings in exposed roles"
series exists anywhere. Options: Adzuna keyword-proxy (`what=graduate`) YoY once 52 weeks of
counts accumulate in `adzuna_state.json` (the plumbing now exists), or India's Naukri JobSpeak
fresher segment (monthly PDF, parse-only). Recommendation: let the Adzuna counts accumulate
starting now; revisit in mid-2027 when a YoY base exists.

**`net_creation` everywhere.** No machine-readable source in any region — WEF Future of Jobs is
biennial PDF-only; Stanford AI Index and OECD.AI publish demand-side proxies, not net creation.
Keep modelled and labelled as a WEF-derived projection. Note the "Net job change" chart on the
dashboard derives its split illustratively from this KPI — in Deep mode that caveat is visible
in the card's source note.

**`ai_mention_postings` / `exposed_posting_index` for India, precision upgrade.** The Indeed
Hiring Lab [ai-tracker](https://github.com/hiring-lab/ai-tracker) still does not cover India
(and covers APAC only via Australia) — Adzuna keyword share is the substitute; note its keyword
net is looser than Hiring Lab's curated taxonomy, which is why the source label says "keyword
proxy". India-native alternatives (Naukri JobSpeak) remain report-only.

## Source-health notes (verified live this review)

- **Anthropic Economic Index**: healthy; the adapter resolves the latest release dynamically
  from the HF tree API, so the newer 2026 releases (e.g. the June "Cadences" report data) are
  picked up automatically — no change needed.
- **Eurostat, ONS, World Bank, data.gov.sg**: all responded normally.
- **ABS**: healthy after the dataflow fix. The API silently ignores the SDMX `+` OR-operator on
  these flows — documented in the adapter so nobody reintroduces the combined-key query.
- **BLS**: fine from CI (keyed); shared-IP unkeyed quota is easily exhausted — do not "test"
  BLS from cloud sandboxes.
- **Authoritative news feeds** (BLS/BBC/Business Standard/Eurostat/CNA/ABC + MIT Tech Review):
  already wired with confidence 4-5 ranking and Google News fallback — the June recommendation
  was implemented before this review.
- **US occupation model workflow (`build-us-model.yml`)**: the July CI fix (O*NET snapshot
  fallback + graceful degrade) is **not** on `origin/main`; the quarterly run on 1 Oct will
  likely fail again on the O*NET fetch (onetcenter.org blocks GitHub's cloud IPs). The fix was
  written and tested in July on the Windows side — worth landing before October.

## Paid options, for completeness

Lightcast (salary premium + AI-skill taxonomy, API), LinkedIn Economic Graph (partner program),
CMIE Consumer Pyramids (India monthly unemployment microdata), Adzuna LMI tier (removes the
free-tier ToS ambiguity). None are required for the current roadmap; Lightcast would be the
first worth pricing if the premium KPI becomes decision-critical.
