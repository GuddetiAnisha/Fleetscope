# FleetScope Real-Data Validation

FleetScope includes a **real public-data methodological validation** using official Statistics Sweden (SCB) vehicle-register data.

## Dataset

**Statistics Sweden (SCB), table TK1001AC** — *Vehicles in use by region and type of vehicles. Year 2002–2025.*

The validation script downloads SCB's public bulk CSV ZIP from:

`https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/en/TAB1278_en.zip`

The successful validation run normalized **90,720 rows** from the official dataset.

## Validation design

This does not claim that Swedish vehicle stock is industrial-equipment population data. It validates the FleetScope estimation methodology on real official registry counts.

1. Historical county data from 2002 through 2022 are used to calibrate geographic source-view coverage.
2. 2023–2025 are kept for later-year holdout evaluation.
3. County codes are deterministically split into three source groups.
4. Each group is coverage-corrected and combined with FleetScope's transparent estimator.
5. Sweden national totals are used as the held-out benchmark.
6. MAE, RMSE, MAPE, interval coverage and benchmark match coverage are reported.

The validated categories were:

- passenger cars
- light lorries
- heavy lorries
- buses

The evaluation contained **36 source observations** and **12 held-out benchmark cells**. All 12 benchmark cells were matched.

All source views originate from one official registry, so they are not independent publishers. This is a real-data methodological stress test, not independent multi-source market validation.

## Validation results

The final successful run produced:

| Metric | Result |
|---|---:|
| Automated tests | **8/8 passed** |
| Normalized SCB rows | **90,720** |
| Calibration period | **2002–2022** |
| Holdout period | **2023–2025** |
| Source groups | **3** |
| Evaluation observations | **36** |
| Held-out benchmark cells | **12** |
| Matched benchmark cells | **12/12** |
| MAE | **1,577.37** |
| RMSE | **3,175.14** |
| MAPE | **0.0451%** |
| Interval coverage | **1.00** |
| Benchmark match coverage | **1.00** |

The low MAPE should be interpreted within this specific validation design: the three source views are geographic partitions derived from the same official registry and are coverage-calibrated using historical years. The result demonstrates that FleetScope's transparent coverage-correction and aggregation methodology can reconstruct later national totals accurately in this controlled real-registry setting. It does **not** establish equivalent accuracy for unrelated industrial-equipment markets or independent commercial data sources.

## Run

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe real_scb_validation.py
```

Outputs are written to `results_real_scb/`:

- `real_sources.csv`
- `real_observations.csv`
- `real_benchmark.csv`
- `real_estimates.csv`
- `real_validation_rows.csv`
- `real_contributions.csv`
- `summary.json`

## Safe portfolio wording

> Built and validated FleetScope on official Statistics Sweden vehicle-register data using historical coverage calibration and 2023–2025 holdout evaluation, achieving 0.045% MAPE with 100% benchmark match and interval coverage across 12 held-out country-category-year cells.

Do not describe this as real industrial-equipment population validation. It is a real registry-data validation of the estimation methodology.
