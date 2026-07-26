# Changelog

All notable changes to petromcp are recorded here. Versions follow
[semantic versioning](https://semver.org/); tags carry no `v` prefix.

## 0.4.0

First release published to PyPI, the Glama directory, and Smithery.

### Fixed

- Truncated LAS files (header sections with no `~ASCII` block) no longer
  crash `summarize_las_curves` or `compare_well_logs`. The 0.3.0 fix only
  covered `read_las_file`; the guard now lives in a shared `safe_index`
  helper that all three tools route through. `compare_well_logs`
  distinguishes "one file has no curve data" from "the depth intervals do
  not overlap" in its flags.
- `read_las_curve` rejects a half-specified depth interval instead of
  silently discarding it. Passing only `depth_start` previously fell back
  to the 500-sample whole-curve downsample, returning a different answer
  than the one requested with no indication.
- The gap percentage no longer divides by a zero depth span, which produced
  a non-finite value in a float field.

### Added

- Every tool declares MCP annotations (`readOnlyHint`, `destructiveHint`,
  `openWorldHint`) and a display title. petromcp only reads, and never
  touches a network; hosts can use this to skip write-approval prompts.
- `glama.json` and `server.json` for directory listings.
- MCPB bundle build (`make bundle`) for Smithery distribution.
- CI now tests Python 3.10 alongside 3.12, matching the declared
  `requires-python` floor.
- Packaging metadata: keywords, trove classifiers, and project URLs.

## 0.3.0 — 2026-05-08

### Fixed

- UTF-8 well names decode correctly. `lasio.read()` defaults to latin-1,
  which turned names like `Pozo-Ñoño` into mojibake. Reads now route
  through `read_lasio`, which tries UTF-8 and falls back to latin-1.
- `read_las_file` returns a degraded `LASSummary` on a truncated LAS
  rather than propagating `lasio`'s `IndexError`.

## 0.2.0 — 2026-05-07

### Added

- `compare_well_logs`: common curves, depth overlap, unit consistency, flags.
- `convert_units`: ft/m, psi/kPa, psi/bar, bbl/m3, degF/degC, mD/m2.
- `petromcp config` subcommands: `show`, `init`, `add-path`, `remove-path`.
- Bad-LAS fixture corpus.

## 0.1.0 — 2026-05-07

Initial release. LAS slice: `read_las_file`, `summarize_las_curves`,
`read_las_curve`, the `qc_a_well_log` prompt, the path allowlist, the
synthetic data generator, a local eval, Claude Desktop install, and a
file-based access log.
