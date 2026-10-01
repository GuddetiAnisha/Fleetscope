# FleetScope Real-Data Validation

FleetScope now includes a **real public-data methodological validation** using official Statistics Sweden (SCB) vehicle-register data.

## Dataset

**Statistics Sweden (SCB), table TK1001AC** — *Vehicles in use by region and type of vehicles. Year 2002–2025.*

The validation script downloads SCB's public bulk CSV ZIP from:

`https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/en/TAB1278_en.zip`

## Validation design

This does not claim that Swedish vehicle stock is industrial-equipment population data. It validates the FleetScope estimation methodology on real official registry counts.

1. Historical county data through 2022 are used to calibrate geographic source-view coverage.
2. 2023–2025 are kept for later-year holdout evaluation.
3. County codes are deterministically split into three source groups.
4. Each group is coverage-corrected and combined with FleetScope's transparent estimator.
5. Sweden national totals are used as the held-out benchmark.
6. MAE, RMSE, MAPE and model interval coverage are reported.

All source views originate from one official registry, so they are not independent publishers. This is a real-data methodological stress test, not independent multi-source market validation.

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
- `summary.json`

## Safe portfolio wording

> Extended FleetScope with a leakage-aware real-data validation pipeline using official Statistics Sweden vehicle-register counts, calibrating coverage on historical years and evaluating population estimates on later held-out years with MAE, RMSE, MAPE and interval coverage.

Do not describe this as real industrial-equipment population validation. It is a real registry-data validation of the estimation methodology.
