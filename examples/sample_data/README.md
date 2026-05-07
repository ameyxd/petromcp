# Synthetic sample data

Every file under this directory is generated, not real. Run

    uv run python -m examples.sample_data.generate

to (re)produce them. The generator is seeded with a fixed integer; the same
seed produces byte-identical output across runs.

`synthetic_well_01.las` contains GR, RHOB, NPHI, DT, CALI over 5000-9000 ft
at 0.5 ft sampling. A small RHOB gap is introduced deliberately so the QC
walkthrough has something to flag.
