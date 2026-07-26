# Changelog

All notable changes to petromcp are recorded here. Versions follow
[semantic versioning](https://semver.org/); tags carry no `v` prefix.

## 0.5.1

### Fixed

- **Every documented install command was broken.** The package declared only
  a `petromcp` console script while the PyPI distribution is
  `petroleum-mcp`, and `uvx <package>` runs the executable whose name matches
  the package. So `uvx petroleum-mcp serve` — the command in the README, the
  install doc, and the Smithery bundle — failed with "An executable named
  `petroleum-mcp` is not provided by package `petroleum-mcp`". The package now
  declares both script names, pointing at the same entry point.
- **The Smithery bundle could never have launched.** Its manifest pinned
  `uvx petroleum-mcp==<version>`, and `uvx` rejects `==` outright: "Not a valid
  package or extra name". The pinned form is `uvx petroleum-mcp@<version>`.
  The bundle build now refuses to produce an artefact containing `==`.

Both slipped through because the release check ran
`uvx --from ./dist/*.whl petromcp serve`, which works, rather than the command
the docs actually give. `tests/test_cli.py::TestConsoleScripts` covers the
alias, and `docs/PUBLISHING.md` records both traps.

## 0.5.0

Synthetic data that a petrophysicist would recognise, and an eval that
asserts against ground truth instead of a copy of it.

### Added

- **Facies-based synthetic generator.** Curves derive from the standard
  relations rather than invented shapes: bulk density from the
  density-porosity relation, transit time from the Wyllie time-average, and a
  clay-bound-water term that produces real neutron-density separation in
  shale. Four facies over a seeded bed sequence, smoothed to model tool
  vertical resolution. Constants are cited textbook typical values and are
  labelled illustrative, not calibrated to any basin.
- **A defect catalogue with recorded ground truth.** Six kinds — `null_gap`,
  `washout`, `spike`, `flatline`, `unit_mismatch`, `missing_curve`. The
  generator writes a `<well>.truth.json` manifest beside each LAS recording
  the bed sequence and every defect it injected.
- **A second synthetic well.** SYNTH-02 partially overlaps SYNTH-01, omits the
  sonic curve, and declares neutron porosity in the wrong units, so
  cross-well comparison has real findings.
- **Eval scenario 02** (compare wells), and scenario 01 rewritten. Neither
  scenario file carries expectations any more: both read the generator's
  manifest, so a generator change cannot leave a stale expectation behind.
  `make eval` now runs every scenario in the directory.
- **`list_supported_units`.** Every convertible pair with its physical
  quantity, derived from the conversion table so it cannot advertise a pair
  `convert_units` would reject. The supported units were previously
  discoverable only by calling the tool wrong and reading the error.

### Notes

The manifest is only useful if it is honest, so `TestManifestDoesNotLie`
reads each written LAS back through the parser and verifies every recorded
defect is actually present. It covers all six kinds, and a new kind that is
not verified fails a coverage test. Without it the eval would be asserting
against a claim rather than a fact.

## 0.4.0

First release published to PyPI, the Glama directory, and Smithery.

### Distribution name

petromcp is published on PyPI as **`petroleum-mcp`**:

    uvx petroleum-mcp serve

PyPI rejects `petromcp` as too similar to `petro-mcp`, an unrelated
petroleum-engineering MCP server — the two normalize to the same string
once separators are collapsed. Only the published distribution name is
affected. The import package, the `petromcp` command, the server name
hosts display, and the repository are all unchanged.

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

- `petromcp serve --allow-path DIR` grants read access to a directory from
  the host's server config, unioned with `~/.petromcp/config.json` rather
  than replacing it. This is what lets a bundle installer show a folder
  picker. It is not a bypass: with no config file and no flag, petromcp
  still reads nothing.
- Every tool declares MCP annotations (`readOnlyHint`, `destructiveHint`,
  `openWorldHint`) and a display title. petromcp only reads, and never
  touches a network; hosts can use this to skip write-approval prompts.
- Server instructions telling the model how to recover from an allowlist
  refusal instead of guessing at neighbouring paths.
- `glama.json` and `server.json` for directory listings, and an MCPB bundle
  build (`make bundle`) for Smithery. Publishing runbook in
  [docs/PUBLISHING.md](docs/PUBLISHING.md).
- CI now tests Python 3.10 alongside 3.12, matching the declared
  `requires-python` floor.
- Packaging metadata: keywords, trove classifiers, and project URLs.

### Changed

- `serverInfo.version` reports petromcp's version. It previously reported
  FastMCP's, which is the field hosts and directories display.
- `__version__` derives from installed package metadata rather than a
  hardcoded constant, which had already drifted a minor version.
- The sdist no longer carries internal design and planning documents
  (178KB down to 41KB).

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
