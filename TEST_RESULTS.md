# Verification

Executed on Python 3.12 with the package versions in requirements.txt.

**7 tests passed (12.43 seconds).**

- Complete synthetic pipeline: 360 accepted observations and 72 estimates.
- Contributions sum to estimates; intervals bracket point estimates.
- Injected outliers detected; synthetic MAPE below 10%.
- CSV alias normalization, invalid-row quarantine and duplicate quarantine.
- Weight exclusion, all-zero weight rejection and disagreement-driven interval widening.
- Monotone service-life sensitivity across all three survival curves; future cohort rejection.
- Catalogue validation and zero-reference MAPE behavior.
- SQLite run persistence and report ZIP contents.
- Streamlit AppTest: initial dashboard render and reliability slider interaction, without app errors.

The UI was checked using Streamlit's headless AppTest, not a manual browser visual inspection. This is a local prototype; no concurrency/load or production security testing was performed.
