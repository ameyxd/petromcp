# Changelog

All notable changes to petromcp are recorded here. Versions follow
[semantic versioning](https://semver.org/); tags carry no `v` prefix.

## 0.7.0

DLIS support. The format the LAS slice's structure was never tested against:
one physical file holds several logging runs, each with several frames, and a
channel name is unique only within a frame.

### Added

- **`read_dlis_file`** — structure only: logical files, frames, index types,
  depth ranges, channel counts. A real DLIS carries hundreds of channels, so
  the cheap structural call comes first.
- **`list_dlis_channels`** — every channel with its frame and logical file,
  which is what makes the result addressable. Optional `frame` filter.
- **`read_dlis_channel`** — one channel's values and index, with the same
  500-sample cap and explicit-interval behaviour as the LAS equivalent. When a
  channel name occurs in more than one frame it **fails and lists the
  candidates** instead of picking one, because the values differ and a guess
  would be a confidently wrong answer.
- **Synthetic DLIS wells**, reusing the facies model and defect catalogue
  unchanged — a DLIS well and a LAS well from the same seed carry the same
  geology, and a test asserts it. One well spans two logging runs, which LAS
  cannot express at all.
- **Bad-DLIS corpus**: every reading tool against every fixture, including a
  LAS file handed to a DLIS tool. A coverage test fails if a new DLIS tool is
  added without being registered.
- **Eval scenario 03**, asserting the DLIS frame layout as well as the defects.

### Changed

- **The access log rotates.** It grew by a line per tool call forever. It is the
  audit trail for a tool whose privacy claim is "you can see everything it
  read", and a file no editor will open is not an audit trail. Defaults to 5 MB
  with five files kept; `max_bytes: 0` disables rotation.
- **`petromcp config add-path` takes effect without a host restart.** The
  allowlist is re-read when the config file changes, and revocation works the
  same way. This does not change who can grant access — anyone able to edit the
  config could already have done so on the next restart — and a change to the
  allowlist is now itself written to the access log. Default-deny is unchanged
  and covered by tests.
- **The CLI validates the config through the same model the server uses.** There
  were two readers: raw `json.loads` here and validated `load_config` there. A
  malformed config written via the CLI surfaced at server start, where the host
  swallows the traceback and reports only that the server would not launch.
  Unknown keys are still preserved, so a newer petromcp's config survives an
  older one's `add-path`.
- `null_gap` writes `np.nan` rather than the LAS `-999.25` sentinel. In a DLIS
  channel that sentinel would be a real measurement of minus nine hundred. Each
  writer now encodes absence in its own convention; the LAS output is unchanged.
- Eval scenarios declare `expect_defect_kinds`. Reading expectations from the
  generator's manifest removes drift but had one blind spot: delete a defect and
  the manifest stops recording it, so the eval stops checking it and still
  reports PASS. Coverage disappeared silently. The declared kinds are asserted
  against the manifest, so that now fails.

### Notes

`dlisio` is a runtime dependency, pinned because it is a C++ extension whose
parse behaviour can shift on a version bump. `dliswriter` is dev-only —
petromcp never writes DLIS.

Two things the DLIS work established by testing rather than reading docs.
`dliswriter` cannot emit more than one logical file, but concatenating its
output with the trailing Storage Unit Labels stripped produces a valid
multi-run file. And a DLIS carrying only a Storage Unit Label loads cleanly with
zero logical files — valid but empty, reported as such rather than refused.

## 0.6.0

### Added

- **Worked walkthroughs** under `examples/walkthroughs/`: a QC pass that finds
  the planted density gap, washout, and gamma ray spike; a cross-well
  comparison surfacing the depth overlap, the missing sonic curve, and the
  neutron unit mismatch; and a short unit-conversion document.

  Every value in them — every depth, every statistic, every JSON block — is
  produced by calling the real tools against a freshly generated well.
  Nothing is transcribed by hand. `make walkthroughs` regenerates them, and
  both the test suite and CI fail if the committed copies drift from what the
  tools currently return, so the most visible docs in the repo cannot rot into
  a documented lie.

  The documents lead with what was deliberately planted, and the manifest
  table proving it, so a reader can check the tools found what was actually
  there instead of taking the output on faith.

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
