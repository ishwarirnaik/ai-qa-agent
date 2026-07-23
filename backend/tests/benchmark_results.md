# Benchmarking & Learning Adaptation Report

This report evaluates the performance of the web-automation system under **dynamic selector drift** conditions on a local mock site (`mock_site.py`) over **20 repeated trials**.
We compare a unified configuration-driven orchestration pipeline across four modes.

---

## Scenario 1: Dynamic Login Flow
*The login page attributes (IDs, placeholders, and buttons) change randomly on every page load.*

### Core Performance Metrics

| Metric | Raw Playwright Script | LangGraph Agent (No Memory) | HMGO-DEEM (Cold Run) | HMGO-DEEM (Warm Run) |
| :--- | :---: | :---: | :---: | :---: |
| **Success Rate** | 0.0% (0/20) | **100.0%** (20/20) | 90.0% (18/20) | 85.0% (17/20) |
| **Mean Runtime (seconds)** | **4.09s** $\pm$ 3.55s | 24.88s $\pm$ 7.02s | 39.04s $\pm$ 43.23s | 200.15s $\pm$ 757.14s |
| **Mean Actions Taken** | 0.0 | 3.0 | 3.0 | 3.0 |
| **Mean Self-Heals** | 0.0 | 0.0 | 0.0 | 0.0 |
| **LLM Calls (8b/70b)** | 0.0/0.0 | 3.0/0.0 | 3.0/0.0 | **2.9/0.0** |
| **Mean Estimated Cost** | **$0.00000** | $0.00045 | $0.00045 | **$0.00043** |
| **Mean Graph Recoveries**| 0.0 | 0.0 | 0.0 | 0.0 |
| **Cache Hit Rate** | N/A | N/A | 0.0% | **100.0%** (on success) |
| **False-Positive Block Rate**| N/A | 0.0% | 5.0% | 10.0% |

---

## Failure Mode Analysis & Distribution

Failures across all modes were categorized into distinct failure signatures:

| Failure Category | Raw Playwright | LangGraph (No Memory) | HMGO-DEEM (Cold) | HMGO-DEEM (Warm) | Total | % of Failures |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Selector Drift Failure** | 20 | 0 | 0 | 0 | 20 | 80.0% |
| **Timeout / Rate Limit Failure** | 0 | 0 | 1 (Trial 17) | 1 (Trial 17) | 2 | 8.0% |
| **Verification / False-Positive Block**| 0 | 0 | 1 (Trial 3) | 2 (Trial 10, 18) | 3 | 12.0% |
| **Navigation Failure** | 0 | 0 | 0 | 0 | 0 | 0.0% |
| **LLM Misreasoning** | 0 | 0 | 0 | 0 | 0 | 0.0% |
| **Execution Crash** | 0 | 0 | 0 | 0 | 0 | 0.0% |
| **Total Failures** | **20** | **0** | **2** | **3** | **25** | **100.0%** |

### Dominant Failure Drivers:
* **Raw Playwright**: Failed 100% of the time due to attribute drift on the form fields.
* **Timeout / Rate Limit**: Trials 17 (Cold & Warm) failed due to hitting Groq's daily/hourly rate limit. The auto-retry backoff slept for up to 3416 seconds before failing, skewing runtimes.
* **Verification (False-Positive)**: Occurred in Trial 3 (Cold) and Trials 10 & 18 (Warm) because the 8b Executor/Planner models generated placeholder strings (e.g. `[Insert browser version]`) in their outputs, which the 8b Reviewer flagged as missing evidence, returning a false-positive `FAIL`/`BLOCKED` status.

---

## Statistical Significance Analysis (Welch's t-test)

We compute Welch's t-test ($p < 0.05$ threshold) across key comparisons:

1. **No Memory Baseline vs. HMGO-DEEM Warm Cache**:
   - Welch's $t$-statistic: **-1.0352**
   - $p$-value: **0.300574** (Significant: **No**)
   
2. **Cold Cache Run vs. HMGO-DEEM Warm Cache Run**:
   - Welch's $t$-statistic: **-0.9501**
   - $p$-value: **0.342078** (Significant: **No**)

3. **Raw Playwright vs. HMGO-DEEM (Cold)**:
   - Welch's $t$-statistic: **-3.6038**
   - $p$-value: **0.000314** (Significant: **Yes** - Playwright is faster but fails)

4. **Raw Playwright vs. HMGO-DEEM (Warm)**:
   - Welch's $t$-statistic: **-1.1580**
   - $p$-value: **0.246850** (Significant: **No** - Outlier runtime masks speed difference)

5. **Raw Playwright vs. HMGO-DEEM Success Rate**:
   - Welch's $t$-statistic (Playwright vs Warm Success): **-10.3763**
   - $p$-value: **< 0.0001** (Significant: **Yes** - HMGO-DEEM is highly superior)

---

## Contribution Validation

* **Persistent Selector Caching (DEEM)**: *Unsupported*. Warm cache runs did not show a statistically significant reduction in runtime ($p \approx 0.30$) or LLM call count ($p \approx 0.32$), and success rates slightly degraded from 100% to 85% due to placeholder-induced verification blocks.
* **Reviewer Verification node**: *Moderately Supported*. Successfully caught placeholder emissions, but acted as a false-positive source due to high sensitivity.
* **Self-Healing and Recovery loops**: *Weakly Supported / Unevaluated*. Playwright's default case-insensitive text matching was robust enough to resolve drifting inputs semantically, meaning the self-healing and graph recovery fallback modules were never triggered during success.

---

## Defensive Academic Paper Statements

* **Paper Thesis**:
  "While hierarchical multi-agent graphs successfully navigate dynamic selector drift where hardcoded scripts fail, persistent selector memory layers do not provide a statistically significant benefit in simple workflows and are bounded by cloud API rate limits and verification constraints."
* **Novelty Statement**:
  "We present an empirical study of the interactions between persistent element caching registries and multi-agent web automation, highlighting the trade-offs of localized self-healing, agentic reasoning, and state verification."
* **Evaluation Summary**:
  "In 20 trials under dynamic selector drift, the agent-based pipeline achieved an 85% to 100% success rate compared to 0% for hardcoded Playwright, but persistent caching failed to reduce LLM calls or wall-clock runtime due to rate-limiting outliers ($p > 0.05$)."
* **Limitations Summary**:
  "The evaluation is limited to a single-page login scenario, and the agent's performance was constrained by 8b model reasoning loops, rate-limit sleep durations of up to an hour, and false-positive verification blocks."

---
*Report generated on: 2026-05-31 14:55:00*
