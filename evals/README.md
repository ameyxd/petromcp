# Evals

Local scenarios that exercise petromcp end-to-end against synthetic data.
Run a single scenario with:

    uv run python -m evals.run_eval --scenario evals/scenarios/01_well_log_qc.yaml

Results land in `evals/results/<date>-<scenario_id>.md`. The directory is
gitignored so personal runs do not pollute the repo; CI uploads its results
as an artifact.
