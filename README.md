# FleetScope

**Multi-Source Industrial Equipment Population Intelligence Platform**

A software-only portfolio prototype for generic industrial equipment market intelligence. This demonstrates competencies relevant to external-source assessment and population estimation. It is **not an implementation of Volvo Penta's thesis or proprietary methodology**, is not affiliated with Volvo, and contains no Volvo branding, internal data, scraped records, or hardware integration. All supplied records are generated synthetic fixtures, including the benchmark; public-style source names describe simulated source types, not actual publishers.

## Quick start

Use Python 3.12 (tested) in a new environment. Extract the ZIP, then open a terminal inside `FleetScope`:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux instead: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local address printed by Streamlit, normally http://localhost:8501. No API keys or external data services are required. Internet access is needed for initial package installation. The app works with the bundled CSVs immediately. It creates `fleetscope.sqlite` in the project directory when started; keep the project in a writable directory.

```bash
python -m pytest -q
python -m fleetscope.data  # regenerate deterministic data, overwrites sample CSVs
python demo.py  # regenerate example_reports without launching Streamlit
```

## What to try

1. Inspect 2025 market estimates and interval bars in Overview.
2. In Sources & scenarios, lower `listings` reliability to zero. The deliberately biased German excavator observations lose their contribution; compare scenario deltas.
3. Inspect source contributions, disagreement and robust outlier flags. Flags are advisory; records are not silently removed.
4. Review MAE, RMSE, MAPE, interval coverage and reference match coverage in Validation.
5. Change survival curve and life scale to explore cohort survivors.
6. Upload CSVs using the supplied schemas. Inspect quarantined rows in Data.
7. Save an estimation run, inspect its timestamp and content fingerprint, and download its full snapshot. Download the report ZIP for estimates, assessments, validation and configuration.

## Data and contracts

The fixtures cover Sweden, Germany, France, Poland, the UK and the US; excavators, generators, forklifts and wheel loaders; 2023–2025; five simulated sources. There are 360 observations, 72 benchmark cells and 624 entrant cohorts. The fixed seed is 42. Market sizes, growth, sampling fractions and noise are invented, not real-world estimates. A strong listings bias is injected for German excavators. The benchmark is held outside the estimator; it never determines weights. Its generation shares simplifying assumptions with the source simulation, so good performance demonstrates plumbing and arithmetic, not real-world validity.

| CSV | Required fields |
|---|---|
| sources.csv | source_id, source_type, geography, year, coverage, granularity, update_frequency, cost_tier, reliability_score |
| observations.csv | source_id, country, category, year, observed_count |
| benchmark.csv | country, category, year, reference_count |
| cohorts.csv | country, category, cohort_year, units |

One catalogue row per source. `year` is the source metadata vintage; coverage is the estimated observed fraction of the target population, in [0.001,1], not a percentage. Reliability is in [0,1]. Cost tiers: free/low/medium/high. Geography, granularity and update frequency are descriptive catalogue fields, not automated eligibility filters. This version assumes coverage and reliability apply uniformly to a source's observations. Split a source into separate IDs if those assumptions vary by market/year.

Observations are stock snapshots, not sales flows. Aliases and whitespace normalize country/category names via dictionaries in `data.py`. This is aggregate category harmonization, not individual machine identity matching; no serial-number records exist. Supported countries and categories are explicitly enumerated in those dictionaries. Unknown aliases, missing fields, negative/nonfinite counts, noninteger years, unknown sources and duplicate source/cell keys are quarantined. All copies of a duplicate key are quarantined to avoid arbitrary first-row selection. Accepted rows continue, with a visible warning and downloadable rejection report. Missing source cells are allowed and weights renormalize over available sources. Benchmarks use canonical keys; cohorts describe original entrants, not already-surviving stock.

## Transparent estimation method

For each country/category/year and source i:

- Adjusted count `x_i = observed_count_i / coverage_i`.
- Raw weight `a_i = reliability_i * coverage_i * exp(-max(estimate_year - source_vintage, 0)/3)`.
- Normalized weight `w_i = a_i / sum(a)`; estimate `mu = sum(w_i*x_i)`.
- Contribution `w_i*x_i` adds exactly to the estimate. A scenario overrides reliability in both weights and uncertainty. All-zero weights fail visibly.
- Disagreement standard deviation `d = sqrt(sum(w_i*(x_i-mu)^2))`; disagreement CV is `d/max(mu,1)`. Flag conflict above 0.20. Range ratio includes every observed source, even scenario-excluded sources, to preserve visibility of raw conflicts.
- Source uncertainty `s_i = x_i * (0.05 + 0.45*(1-reliability_i) + 0.20*(1-coverage_i))`.
- Combined uncertainty `s = sqrt(sum(w_i*s_i^2) + d^2)`; interval `[max(0,mu-1.96*s), mu+1.96*s]`.

These are **model-based 95% uncertainty intervals**, using a normal approximation and explicit heuristic error assumptions. They are not calibrated frequentist confidence intervals or guarantees. Systematic uncertainty is retained instead of shrinking by the number of potentially correlated sources. No aggregate interval is calculated without a covariance assumption. A single source still has an uncertainty term. An all-zero observed stock produces a zero interval under this multiplicative model; this cannot establish real-world absence and needs an additive detection-error model in a production extension.

Effective source count is `1/sum(w_i^2)`, not a claim of independence. Outliers deviate from the unweighted source median by more than `max(3*1.4826*MAD, 20%*max(median,1))`. The relative floor handles zero MAD. Small source samples limit detection. No automatic outlier deletion is performed.

Validation uses only matching unique keys, reports match coverage separately, and excludes zero reference counts from MAPE while counting them. MAE and RMSE remain in equipment units. Interval coverage is the fraction of matched reference values in the interval. There is no training/test split because this model is not fitted to the benchmark. Pandas/NumPy provide transparent arithmetic; scikit-learn is included for extension but is deliberately unnecessary for five-source robust detection.

## Survival and recommendations

For cohort age t, Weibull survival is `exp(-(t/life)^shape)`, exponential survival is `exp(-t/life)`, and fixed retirement is `1(t<life)`. Cohort entrants times survival probability gives expected surviving stock. Life is a scale parameter, not mean lifespan for Weibull. Future cohorts and invalid numeric inputs are rejected. These configurable curves are not fitted from observed failure/censoring data. The survival view is an independent bottom-up stock scenario, not an extra triangulation source; this avoids double-counting without a validated linkage.

Recommendation score: 0.4 reliability + 0.3 coverage + 0.2 freshness + 0.1 affordability. Freshness decays exponentially with a three-year scale relative to the selected assessment year. Affordability values are 1/.75/.45/.15 for free/low/medium/high. Edit coefficients in `rank_sources` for another policy. Ranking is a transparent heuristic, not an acquisition ROI model.

## Architecture

```text
CSV inputs -> data.py (contracts, aliases, quarantine)
           -> model.py (triangulation, validation, survival, ranking)
           -> app.py (Streamlit + Plotly charts and scenarios)
           -> storage.py (atomic SQLite immutable run snapshots)
           -> reporting.py (portable CSV/JSON/Markdown ZIP reports)
```

SQLite stores UTC timestamps, UUIDs, model/scenario configuration, SHA-256 fingerprints and complete input/output snapshots as JSON. Inserts are atomic; existing runs are never overwritten. Fingerprints support comparison, not tamper-proof certification. Historical snapshots can be downloaded for inspection. The local app is single-user, without authentication, cloud deployment, migrations or production access controls. Charts are included; geographic maps are omitted to keep visualization offline and dependency-light.

## Competency mapping and intentional adaptation

| Relevant competency | Portfolio evidence |
|---|---|
| Source discovery/assessment framework | Configurable inventory, metadata contracts and explainable source ranking |
| Data engineering | CSV ingestion, normalization, quarantine, aggregate harmonization and SQLite persistence |
| Statistical triangulation | Coverage correction, reliability weights, uncertainty and conflict diagnostics |
| Validation and critical analysis | Synthetic held-out reference, error metrics, interval/match coverage and visible assumptions |
| Reproducible software | Modular Python, seeded fixtures, automated tests and immutable run snapshots |
| Decision support | Interactive scenarios, source contributions, cohort survival and downloadable reports |

The adaptation studies multiple equipment categories rather than one manufacturer's industrial-engine fleet. It adds a reusable software platform, scenario UI, persistence and cohort exploration. It does not perform actual external-source discovery, commercial source procurement, internal-estimate validation or engine/OEM attribution. Production extensions would require licensed source ingestion, calibrated coverage, correlated-error modeling, censored-lifetime fitting and external validation.
