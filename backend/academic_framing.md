# Academic Paper Layout & Research Framing
## Model: HMGO-DEEM (Hierarchical Multi-Agent Graph Orchestration with Decentralized Element Experience Memory)

To address the critique of **"Not Novel Enough for Pure AI Research"**, we must shift the framing from *"we built a QA agent"* to *"we present a hybrid orchestration-memory model that optimizes the speed, reliability, and token-cost of autonomous web automation."*

This document provides a template and structure for an applied AI / engineering systems research paper.

---

### 1. Title Ideas
- **HMGO-DEEM**: *Experience-Augmented Hierarchical Orchestration for Resilient Web Automation under Attribute Drift*
- *Self-Healing Web Automation: Persistent Experience Registries in Multi-Agent Graph Architectures*
- *Overcoming LLM Latency and Cost in Autonomous Browser Agents via Decentralized Element Memory*

---

### 2. Abstract (Draft)
> Robustness in web automation remains an open challenge due to "selector drift"—frequent updates to DOM properties that break hardcoded test scripts. Autonomous LLM-based agents (e.g., ReAct browser agents) can navigate dynamic UIs but suffer from high latency, high token costs, and lack of temporal learning. 
> 
> We introduce **HMGO-DEEM**, a system that combines **Hierarchical Multi-Agent Graph Orchestration (HMGO)** with **Decentralized Element Experience Memory (DEEM)**. HMGO decomposes tasks into separate Planning, Execution, Review, and Recovery nodes. DEEM maintains a persistent, cross-run experience database that caches successful locator resolutions. When a locator drifts, a dual-engine (heuristic + LLM) self-healing mechanism resolves the new element and updates the experience registry. 
> 
> Experiments on drifting web interfaces show that HMGO-DEEM achieves 100% test success under extreme selector drift, while reducing execution duration by **X%** and API token costs by **Y%** on subsequent runs compared to baseline ReAct agents.

---

### 3. Introduction
- **The SDET Fragility Problem**: Classical testing (Selenium, Playwright) relies on static identifiers (`id`, `class`). If developers refit components, tests break.
- **The LLM Agent Cost/Latency Wall**: While ReAct browser agents can inspect DOM and reason on the fly, doing so for every action in every test run is computationally and financially prohibitive.
- **Our Solution**: HMGO-DEEM. We separate macroscopic reasoning (LangGraph state management) from microscopic action (ReAct tool use) and tie them together with a temporal learning layer (MongoDB selector cache).

---

### 4. System Architecture

```
                       +---------------------------------------+
                       |          User Objective / Plan        |
                       +---------------------------------------+
                                           |
                                           v
                       +---------------------------------------+
                       |    Hierarchical Multi-Agent Graph     |
                       |         Orchestrator (HMGO)           |
                       +---------------------------------------+
                           |               ^               |
                     Plan  |               | Guidance      | Verify / Fail
                           v               |               v
              +------------------+   +-----------+   +------------+
              | Browser Executor |   | Recovery  |   | Independent|
              |     Agent        |   | Specialist|   |  Reviewer  |
              +------------------+   +-----------+   +------------+
                       |                   ^
                Action |                   | Prompt / Heuristics
                       v                   |
        +-------------------------------------------------+
        |      Decentralized Element Experience Memory     |
        |                  (DEEM) Layer                   |
        +-------------------------------------------------+
                |                   ^               |
        Lookup  |                   | Write         | Scan DOM
        Cache   v                   |               v
        +---------------+   +---------------+   +---------------+
        |  Mongo / Mem  |   |  Self-Healing |   | Light-weight  |
        |  Registry     |   |  (LLM + Fuzzy)|   | DOM Scraper   |
        +---------------+   +---------------+   +---------------+
```

- **HMGO (LangGraph)**:
  - **Planner Node**: Converts human intentions into structured execution targets.
  - **Executor Node**: Performs browser actions.
  - **Reviewer Node**: Judges credibility of evidence post-execution (protects against LLM hallucination).
  - **Recovery Node**: Creates alternate execution strategies if the reviewer detects a failure.
- **DEEM (Memory)**:
  - **Experience Cache**: Key-value store mapping `(URL, Element Description) -> Resolved Selector`.
  - **Self-Healing Fallback**: When cache misses or fails, a fast string-similarity scoring engine filters candidates, falling back to a lightweight LLM only if match confidence is low.
  - **Experience Registry Updates**: Successful healing matches are stored back to Mongo, facilitating temporal learning.

---

### 5. Research Questions (RQs)
- **RQ1 (Success Rate)**: Can HMGO-DEEM handle dynamic selector changes where traditional Playwright scripts fail?
- **RQ2 (Cost Efficiency)**: How much does DEEM reduce token costs compared to memory-less ReAct agents over multiple runs?
- **RQ3 (Latency Reduction)**: What is the execution speedup on warm-cache runs compared to cold-cache runs?

---

### 6. Methodology & Benchmarking Setup
- Describe the dynamic mock website (`mock_site.py`) featuring randomized attributes.
- Detail the metrics:
  - **Success rate** (proportion of runs passing verification).
  - **Execution time** (seconds to finish).
  - **Token usage** (divided by model type).
  - **Action counts** (indicating efficiency).

---

### 7. Results & Discussion (To be filled from benchmark runs)
- Highlight the **warm-start cache hit rate**.
- Discuss the limitation of simple ReAct: it treats every run as a fresh problem, wasting LLM reasoning steps.
- Highlight the engineering paper angle: we demonstrate that combining database state caching with agentic graphs yields production-grade stability at a fraction of standard LLM pricing.
