# FleetScope
## Multi-Source Industrial Equipment Population Intelligence Platform

FleetScope is a Python-based application that estimates how many industrial machines may be operating in different countries. It combines incomplete equipment counts from several sources, adjusts those counts to account for how much of the market each source covers, and gives more weight to sources considered reliable and recent. It also shows uncertainty, checks estimates against reference data, explores how equipment populations change with age, and presents everything in a Streamlit dashboard.

This project is a **portfolio prototype**, not a live industrial-equipment registry. Its main industrial-equipment data is synthetic. A separate experiment validates the estimation methodology with official Swedish vehicle-registration data, which is real but is **not** industrial-equipment population data.

## 1. The problem I wanted to address

Imagine a company trying to answer a seemingly straightforward question: How many excavators are operating in Sweden, or how many forklifts are in use in Germany?

There might not be a single database with that answer. Registration records, industry surveys, sales information, and equipment listings may each reveal only part of the market. They may also report different figures because they were collected for different purposes, at different times, or over different geographic areas.

Simply adding all reported counts would risk double-counting machines. Trusting a single source would ignore potentially useful information. FleetScope explores a more careful approach: work out what each source's observation means, adjust it for estimated coverage, combine the adjusted figures based on source quality, and explain the uncertainty in the result.

A second question follows naturally: even if machines entered service several years ago, how many might still be operating today? FleetScope includes a separate equipment-survival calculation to explore that question.

## 2. What I built

The application supports a complete workflow:

1. Read CSV files describing sources, equipment observations, reference counts, and equipment cohorts.
2. Check the input files, standardize recognized names, and separate invalid records.
3. Correct each source's observed count for its assumed share of the market.
4. Combine those adjusted counts using reliability-, coverage-, and freshness-based weights.
5. Calculate uncertainty and highlight unusual or conflicting observations.
6. Compare estimates with benchmark counts using error metrics.
7. Explore survival assumptions for machines introduced in earlier years.
8. Rank information sources by reliability, coverage, freshness, and affordability.
9. Display results in an interactive dashboard.
10. Save estimation runs in SQLite and export reports.

The implementation is deliberately transparent. Rather than using a trained black-box predictor for the main estimate, the system exposes the source counts, correction factors, weights, and contributions behind every result.

## 3. Data used in the main application

The bundled demonstration data is generated with a fixed random seed of 42, making the example repeatable. It covers **Sweden, Germany, France, Poland, the United Kingdom, and the United States**; **excavators, generators, forklifts, and wheel loaders**; and observation years **2023–2025**.

There are **five simulated source types**, **360 observations**, **72 benchmark cells**, and **624 equipment cohorts**. The market sizes, source coverage values, growth assumptions, and noise are invented for testing. A deliberately biased listing source for German excavators makes it possible to demonstrate what happens when a source is down-weighted.

Four input files organize the data:

| File | What it contains | How it is used |
| --- | --- | --- |
| `sources.csv` | Source identity, type, coverage, reliability, reference year, update frequency, and cost tier | Describes the source and provides estimation weights |
| `observations.csv` | Source, country, equipment category, observation year, and observed machine count | Provides the partial equipment counts |
| `benchmark.csv` | Country, category, year, and reference count | Evaluates estimates; it is not used to choose source weights |
| `cohorts.csv` | Country, category, year equipment entered the population, and original number of units | Supports the separate survival scenarios |

The observation figures are **stock snapshots**—counts of machines believed to be present—not annual sales totals. The cohort values represent original entrants, rather than machines already known to have survived.

## 4. Preparing and checking the input data

I implemented data preparation in `data.py`. Before making estimates, the application checks that the CSVs contain the necessary fields and that source information is sensible.

Different files may refer to a country or equipment category using slightly different names. The preprocessing logic standardizes supported aliases and extra whitespace so matching records use consistent names. This is **name and category normalization**, not numerical feature scaling for machine learning.

I also check for missing fields, invalid or negative counts, non-integer years, unknown source identifiers, unsupported aliases, and duplicate observations for the same source/country/category/year combination.

Bad records are not silently deleted. They are placed in a **quarantine report** that users can inspect or download, while accepted records continue through the pipeline. Duplicate source/cell keys are quarantined rather than arbitrarily keeping the first copy. Missing source observations are allowed; the estimator rebalances weights across the sources that are actually available.

This stage matters because even a sound estimation formula can produce misleading results when the inputs are inconsistent.

## 5. Adjusting partial observations for coverage

A source rarely sees the entire equipment market. Suppose it reports 4,000 excavators, but it is assumed to cover only 40% of the market. Treating 4,000 as the full population would undercount the machines.

FleetScope calculates an **adjusted count**:

```text
Adjusted count = Observed count / Coverage
4,000 / 0.40 = 10,000
```

The source therefore suggests a total population of around 10,000 machines. This result is only as meaningful as the assumed coverage fraction: if that fraction is wrong or changes over time, the estimate may also be wrong.

For the main synthetic application, the coverage values come from the source catalogue. For the separate real-data experiment, I calculate coverage using historical Swedish vehicle counts, as explained later.

## 6. Combining estimates from multiple sources

A coverage-adjusted count is still only one source's estimate. I combined the adjusted counts with **weighted statistical estimation** (also called triangulation).

Each source receives a raw weight based on:

- **Reliability:** how trustworthy the source is assumed to be;
- **Coverage:** how much of the market the source sees;
- **Freshness:** how old the source's metadata is relative to the year being estimated.

In `model.py`, the raw weight is:

```text
Raw weight = reliability × coverage × exp(-max(estimate_year - source_year, 0) / 3)
```

Raw weights are normalized so they add to one. Each source's adjusted count is multiplied by its normalized weight, and these contributions are summed.

For instance, consider a simplified example:

| Source | Adjusted equipment count | Normalized weight | Contribution |
| --- | ---: | ---: | ---: |
| A | 10,000 | 50% | 5,000 |
| B | 12,000 | 30% | 3,600 |
| C | 9,000 | 20% | 1,800 |
| **Combined estimate** | | **100%** | **10,400** |

This table is an explanation of the arithmetic, **not an actual FleetScope data row**. The real application calculates the weights using the source metadata instead of manually assigning them.

Users can inspect each source's contribution, which makes it easier to understand why the estimate changed when a source is given less importance. If every source in a cell has a zero weight, the estimator reports an error instead of quietly returning a result.

## 7. Showing uncertainty and source disagreement

The combined estimate should not look more certain than the underlying information. Different sources can disagree, and coverage and reliability are themselves assumptions.

FleetScope calculates a measure of the spread of adjusted source counts around the combined estimate. It also calculates a source-level uncertainty term based on adjusted count, reliability, and coverage. These components produce a **model-based uncertainty interval** with a lower and upper bound.

The implementation uses a normal-approximation multiplier of 1.96, but the assumed error terms are heuristic. This should **not** be described as a statistically calibrated 95% confidence interval or a guarantee that the true value falls inside it.

The application flags strong disagreement when the weighted disagreement coefficient exceeds 0.20. It also uses the median and **Median Absolute Deviation (MAD)** to identify unusually distant source observations. An outlier is **flagged, not automatically removed**, so a user can still inspect the original disagreement.

The dashboard reports intervals for individual market/category/year cells. It deliberately avoids inventing one aggregate interval across markets without assumptions about how errors are related.

## 8. Evaluating the synthetic estimates

I kept synthetic reference counts in `benchmark.csv` and used them to evaluate the outputs. They are not used to fit the estimator or decide its source weights. Because the estimator is not trained against the benchmark, there is no conventional training/testing split for the main synthetic pipeline.

The evaluation matches estimates to reference counts using country, category, and year. It reports:

- **MAE (Mean Absolute Error):** average absolute error in equipment units.
- **RMSE (Root Mean Squared Error):** error in equipment units, with more influence from large mistakes.
- **MAPE (Mean Absolute Percentage Error):** average percentage error where the reference is nonzero.
- **Benchmark match coverage:** fraction of reference cells with a matching estimate.
- **Interval coverage:** fraction of matched reference counts falling within the model's uncertainty interval.

The saved synthetic results in `metrics.json` are:

| Metric | Result |
| --- | ---: |
| MAE | 988.49 |
| RMSE | 1,491.87 |
| MAPE | **2.0161%** |
| Matched benchmark cells | **72** |
| Benchmark match coverage | **100%** |
| Interval coverage | **100%** |

The roughly 2.02% MAPE shows good agreement **within this generated example**. The reference and observation-generation process share simplifying assumptions, so this does not prove the same performance on independent real industrial-equipment records.

## 9. Exploring how many older machines survive

Knowing the number of machines that entered service is different from knowing how many remain. I added a separate cohort-survival module to explore this.

A **cohort** is a group of machines introduced in a particular year. For example, 1,000 forklifts introduced in 2015 form one cohort. The application calculates their age at the chosen assessment year and multiplies the original units by a survival probability.

It supports three configurable models:

**Weibull:** survival probability is `exp(-(age / life_scale)^shape)`. The shape controls how the retirement pattern changes with age.

**Exponential:** survival probability is `exp(-age / life_scale)`. This represents a constant hazard rate.

**Fixed retirement:** machines count as surviving while their age is below the chosen service life, and as retired at or above it.

If a cohort contains 1,000 machines and its assumed survival probability is 60%, the expected remaining population is 600.

The service-life values and Weibull shape are selectable in the dashboard. These curves have **not been fitted to observed machine failures or retirements**; they are useful scenarios, not empirically validated life predictions.

Survival results are kept separate from the main triangulated estimate to avoid treating the same population as a second independent source.

## 10. Ranking information sources

Alongside equipment estimates, the application evaluates possible source usefulness with a simple, explainable scoring system:

| Factor | Share of recommendation score |
| --- | ---: |
| Reliability | 40% |
| Coverage | 30% |
| Freshness | 20% |
| Affordability | 10% |

Freshness decreases with source age. Affordability is mapped from the source's cost tier (free, low, medium, or high). The ranked table helps users see which sources perform better against those chosen priorities.

This is a **configurable decision-support heuristic**, not a machine-learning model and not a full cost-benefit or return-on-investment calculation.

## 11. The separate real-data validation

After building the prototype, I also checked the estimation methodology using **official Statistics Sweden (SCB)** vehicle-registration information. The project uses the SCB table `TK1001AC`, containing vehicles in use by region and vehicle type for **2002–2025**.

This experiment validates the **method**, not an actual industrial-equipment population. The four evaluated vehicle categories are passenger cars, light lorries, heavy lorries, and buses.

The successful run normalized **90,720 rows**. I grouped Swedish counties deterministically into **three geographic source views**. These act like partial observations of the national vehicle population.

### Historical coverage calibration, 2002–2022

For each county group, I compared its historical vehicle counts with corresponding Swedish national counts. Across the calibration period, the summed group counts were divided by the summed national counts to estimate the group's coverage fraction. These historical coverage estimates were then held fixed for evaluation.

### Later-year holdout, 2023–2025

I used partial county counts from **2023–2025** as observations, corrected them using historical coverage fractions, combined the adjusted estimates through the FleetScope estimator, and compared the outputs with actual national totals for the same years.

This separation also matters for **data leakage**. Data leakage occurs when information from the intended evaluation period influences the model or parameters being evaluated. In this experiment, the **2023–2025 national reference totals were not used to calculate the historical coverage fractions**. They were reserved to measure the accuracy of later-year estimates.

The experiment used **36 source observations** across **12 held-out benchmark cells**, with all 12 matched.

| Metric | Real SCB validation result |
| --- | ---: |
| MAE | 1,577.37 |
| RMSE | 3,175.14 |
| MAPE | **0.0451%** |
| Benchmark match coverage | **100% (12/12)** |
| Interval coverage | **100%** |
| Automated tests noted in validation report | **8/8 passed** |

The very low MAPE indicates that historical coverage calibration reconstructed later national totals closely **under this specific design**.

There is a crucial qualification: the three county source views were **all derived from the same SCB registry**, not three independent publishers. Their errors and assumptions may be related. This was a controlled real-registry stress test, **not** proof that the method reaches 0.0451% MAPE on unrelated industrial equipment sources.

The validation script is `real_scb_validation.py`; its documentation is in `REAL_DATA_VALIDATION.md`.

## 12. Interactive Streamlit dashboard

To make the calculations usable without manually running scripts, I developed a local **Streamlit** application with interactive **Plotly** charts. It has six sections:

**Overview:** country- and category-level population estimates, interval bars, selected-year totals, source contributions, conflict indicators, and outlier flags.

**Sources & scenarios:** editable source information, source-reliability sliders, rankings, and comparisons between a baseline and a changed scenario. The generated German excavator listing bias provides a practical example: giving that source zero reliability removes its weight from the combined estimate.

**Validation:** reference-versus-estimate comparisons, MAE, RMSE, MAPE, interval coverage, and benchmark match coverage.

**Survival:** Weibull, exponential, and fixed-retirement scenario controls, with surviving-equipment tables and charts.

**Data:** accepted observations, quarantined records, downloadable rejection details, sample CSVs, and support for CSV uploads following the documented structure.

**Run history:** previous saved calculations with unique IDs, timestamps, and downloadable input/output snapshots.

The dashboard uses the bundled CSVs by default, so no external API key is needed to explore the synthetic demonstration.

## 13. Saving results and generating reports

The application uses **SQLite** to save estimation runs. A run includes its inputs, selected settings, calculations, source assessments, and validation outputs. Entries are written atomically and earlier saved runs are not overwritten.

The stored information includes a timestamp, unique identifier, and a **SHA-256 content fingerprint** to help compare snapshots. A fingerprint supports repeatability and comparison; it is not a tamper-proof certification.

Users can download a complete JSON snapshot or a ZIP containing portable outputs such as estimates, contributions, validation information, and configuration.

## 14. Technologies and code organization

| Technology | Role |
| --- | --- |
| Python | Application and statistical logic |
| Pandas | Reading, cleaning, joining, and grouping tabular data |
| NumPy | Numerical estimation and uncertainty calculations |
| Streamlit | Interactive local web interface |
| Plotly | Interactive visualization |
| SQLite | Saved-run history |
| Pytest | Automated verification |
| Requests | Retrieving the public SCB validation dataset |
| CSV / JSON / ZIP | Inputs, snapshots, and downloadable reports |

The key files are:

- `data.py`: accepted/rejected record handling, contracts, and aliases.
- `model.py`: estimation, validation, uncertainty, survival, and source ranking.
- `app.py`: interactive dashboard.
- `storage.py`: SQLite persistence.
- `reporting.py`: report packaging.
- `real_scb_validation.py`: official Swedish vehicle-data methodological validation.
- `metrics.json`, `TEST_RESULTS.md`, `REAL_DATA_VALIDATION.md`: recorded evaluation and verification evidence.

### Run locally

Use a Python 3.12 environment and run:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app normally opens at `http://localhost:8501`.

To run tests or the real-data experiment:

```bash
python -m pytest -q
python real_scb_validation.py
```

The real-data script downloads a public SCB dataset and writes results to `results_real_scb/`.

## 15. Testing and reliability checks

The repository documents tests for the synthetic end-to-end pipeline, coverage weighting, weight exclusion, conflicting-source behavior, outlier detection, CSV cleaning, duplicate quarantine, survival sensitivity, SQLite persistence, ZIP reports, and basic Streamlit interactions.

These checks show that the code behaves as intended in the tested scenarios. They are not equivalent to production security, load testing, or independent commercial-data validation.

## 16. What the project demonstrates

FleetScope brings together several practical skills: structured data ingestion, validation and data-quality handling, statistical estimation, explainable aggregation, uncertainty communication, held-out evaluation, scenario analysis, interactive visualization, and reproducible reporting.

One of its strongest aspects is that it makes the estimate **traceable**. Instead of only showing a population number, the system allows users to inspect the observations, correction factors, source weights, disagreements, and assumptions that led to it.

The project is best described as a **transparent statistical decision-support system**. Although machine-learning libraries may be available for future extensions, the current main estimator is **not a trained Random Forest, neural network, or other machine-learning predictor**.

## 17. Limitations and possible next steps

FleetScope remains a prototype. The main equipment dataset is synthetic; coverage and reliability are assumed rather than fully calibrated from independent industrial sources; uncertainty intervals use heuristic error assumptions; and survival models are not fitted to observed retirement histories. The real SCB experiment uses partitions of one registry. The dashboard is a local single-user application without production authentication or cloud deployment.

Useful future extensions include licensed industrial data ingestion, historically calibrated source reliability, better modeling of correlated source errors, fitted survival models using retirement/failure records, time-series population forecasts, and production-ready deployment and access control.

## Conclusion

FleetScope explores how incomplete and sometimes conflicting records can be transformed into understandable equipment population estimates. It starts with data cleaning, corrects partial observations for coverage, combines them based on source quality, displays uncertainty, and checks the results against reference counts. It also provides survival scenarios, source rankings, a usable dashboard, and saved reports.

The synthetic benchmark shows that the implemented pipeline works under controlled assumptions. The official Swedish vehicle-register experiment adds a real-data methodological check while making its limitations explicit. Together, these components provide a foundation for extending FleetScope into a more realistic industrial fleet intelligence platform.

---

**Repository:** https://github.com/GuddetiAnisha/Fleetscope

**Related documentation:** [README](README.md) · [Real-data validation](REAL_DATA_VALIDATION.md) · [Test results](TEST_RESULTS.md)
