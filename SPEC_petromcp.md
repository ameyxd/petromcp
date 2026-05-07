# SPEC: petromcp

> An MCP server that lets Claude Code, Cursor, and Codex CLI read petroleum data formats natively. LAS well logs, DLIS, SEG-Y headers, pump cards. Synthetic data only by default.

**Project name:** `petromcp`
**Repo slug:** `petromcp`
**License:** MIT
**Primary language:** Python (>=3.10)
**Distribution targets:** Claude Desktop, Claude Code, Cursor, Windsurf, Codex CLI, any MCP-compatible host
**Target build time:** one focused weekend (~14 hours of build, ~4 hours of polish + launch prep)

---

## What this is

`petromcp` is a Model Context Protocol server that exposes the binary and semi-structured data formats the petroleum industry actually uses (LAS well logs, DLIS, SEG-Y seismic headers, pump dynacard CSVs) as MCP tools. Drop it into your `.claude.json` or Claude Desktop config and Claude can read your well log and answer questions about it without you needing to first load it into Python and copy-paste the relevant rows into chat.

The audience is narrow but real: petroleum engineers, geophysicists, production engineers, reservoir engineers, and the data scientists who work alongside them. Sub-segment: the increasing number of these professionals who are using AI copilots for daily work but find that the copilots can't read the file formats their work actually lives in.

This project is honest about its star ceiling. The petroleum engineering community is not r/ClaudeAI. The path to traction is different (SPE forums, LinkedIn, JPT coverage) and the numbers are smaller (200-800 stars over six months is the realistic range, not 5000). What it gives up in raw stars it gains in:
- Genuinely novel work (no one else has shipped a credible petroleum-format MCP server as of this writing)
- A real audience that benefits, not vanity metrics
- A natural angle for press coverage (JPT, Hart Energy, RigZone) because mainstream petroleum publications are starved for AI-tooling stories

## Why this matters in 2026

The MCP ecosystem has 500+ servers and 97M monthly SDK downloads as of early 2026. Most servers cover horizontal needs (databases, web search, code hosts, productivity tools). Vertical industry MCP servers exist but are rare; the few that have shipped (Willi MaKo Knowledge Service for German energy market regulations is a noteworthy outlier) demonstrate that vertical depth gets traction within its industry.

The petroleum industry has a stack of file formats that are obscure to outsiders but daily reality to insiders:
- LAS (Log ASCII Standard): well log data, the most common format, well-supported by `lasio`.
- DLIS / RP66: binary log data, more complex than LAS, supported by `dlisio` (open-sourced and maintained by Equinor and previously contributors at Schlumberger).
- SEG-Y: seismic data; full data is huge, but headers are tractable and useful in conversation. `segyio` handles this.
- Dynacard / pump card data: artificial-lift diagnostic data. Not standardized; commonly stored as CSV time-series.
- WITSML: real-time drilling data XML. Out of scope for v1, listed as v2.

A working MCP server that handles the first four formats fills a real gap. No competitor exists. The technical lift is modest because the parsers are mature open source. The marketing lift requires care because the audience does not live on the same channels as a typical AI tooling launch.

## Non-goals (do NOT build these in v1)

1. Full SEG-Y trace data. Headers and a sampled subset only. Full SEG-Y files are gigabytes; trying to put trace data into LLM context is wrong on multiple levels.
2. WITSML. Real-time streaming is a different problem; defer to v2.
3. Reservoir simulation outputs (Eclipse RST, Intersect, etc.). Tempting but each format is its own project.
4. Production data warehouses (PI, OSI, IP21). Different integration story.
5. Visualization beyond basic Plotly HTML. No 3D, no interactive cross-sections. Out of scope.
6. Auto-detection of proprietary or sensitive data. Users are responsible for what they point this at; documentation is explicit.
7. Cloud-hosted version. Local stdio transport only in v1. Streamable HTTP comes in v2 with auth.

## Strict data privacy stance (read this carefully)

The petroleum industry takes data confidentiality seriously. Operators do not want their well logs leaving their security perimeter. petromcp must be unambiguous about this:

- **The server runs locally.** stdio transport, on the user's machine. No data leaves unless the LLM host (Claude Desktop, Claude Code) sends it to Anthropic, and that is governed by the host's privacy policy, not petromcp.
- **Sample data is synthetic.** Every example file in the repo is generated, not real. Documented synthesis script in `examples/sample_data/generate.py`.
- **A `--read-only` flag and a path allowlist.** v1 ships with the server only being able to read files in directories the user explicitly lists in config. Default deny.
- **A `DATA_PRIVACY.md` document is prominent.** Top-level link in the README, first thing in the docs index. Not buried.

This is not paranoia. It is the price of admission to the audience.

## Architecture

A single FastMCP Python server with five tool categories:

**Tools (model-controlled):** the LLM decides when to call these.
- `read_las_file(path: str) -> LASSummary`
- `summarize_las_curves(path: str) -> CurveSummary`
- `read_las_curve(path: str, curve_name: str, depth_range: Optional[DepthRange]) -> CurveData`
- `read_dlis_file(path: str) -> DLISSummary`
- `list_dlis_channels(path: str) -> ChannelList`
- `read_dlis_channel(path: str, channel_name: str, frame: Optional[str]) -> ChannelData`
- `extract_segy_headers(path: str) -> SEGYHeaders`
- `parse_pump_card_csv(path: str) -> PumpCardSummary`
- `compare_well_logs(path_a: str, path_b: str) -> ComparisonReport`
- `convert_units(value: float, from_unit: str, to_unit: str) -> float`

**Resources (app-controlled):** the host application can request these.
- `well_log_plot://path/<curves>` returns a Plotly HTML payload of the requested curves.
- `pump_card_plot://path` returns a Plotly HTML payload of the surface and pump dynacards.

**Prompts (user-controlled):** the user can invoke these by name.
- `qc_a_well_log`: a reusable prompt template that walks Claude through standard well log QC (gaps, units, value ranges, expected curve relationships).
- `diagnose_pump_card`: walks Claude through standard pump card classification (gas interference, fluid pound, tubing leak, etc.).

The output models are Pydantic schemas, defined in `src/petromcp/models/`, kept lean. LLM hosts have token budgets; an output that is 30K tokens of curve data is not useful. Every tool returns either a summary (default) or a specific slice the user asked for.

## File layout

```
petromcp/
├── README.md
├── LICENSE
├── pyproject.toml
├── install.sh
├── src/
│   └── petromcp/
│       ├── __init__.py
│       ├── server.py                  # FastMCP setup; ties tools together
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── las.py                 # LAS file tools (uses lasio)
│       │   ├── dlis.py                # DLIS file tools (uses dlisio)
│       │   ├── segy.py                # SEG-Y header tools (uses segyio)
│       │   ├── pump_cards.py          # Pump card CSV tools
│       │   ├── compare.py             # Cross-well comparison
│       │   └── plotting.py            # Plotly HTML resource generation
│       ├── models/
│       │   ├── __init__.py
│       │   ├── las_models.py
│       │   ├── dlis_models.py
│       │   ├── segy_models.py
│       │   ├── pump_card_models.py
│       │   └── shared.py              # DepthRange, Unit, etc.
│       ├── prompts/
│       │   ├── qc_a_well_log.py
│       │   └── diagnose_pump_card.py
│       ├── utils/
│       │   ├── path_validator.py      # Allowlist enforcement
│       │   ├── units.py               # ft/m, psi/kPa, bbl/m3 conversions
│       │   ├── cache.py               # Memoize parsed files
│       │   └── summarizer.py          # Truncate/summarize large outputs
│       └── config.py
├── examples/
│   ├── sample_data/
│   │   ├── README.md
│   │   ├── generate.py                # Synthesizes all sample files
│   │   ├── synthetic_well_01.las
│   │   ├── synthetic_well_02.las      # Different curves, for comparison
│   │   ├── synthetic_well.dlis
│   │   ├── synthetic_seismic.sgy      # Headers only, small file
│   │   └── synthetic_pump_card.csv
│   ├── walkthroughs/
│   │   ├── 01_inspect_a_well_log.md
│   │   ├── 02_compare_two_wells.md
│   │   ├── 03_diagnose_pump_card.md
│   │   └── 04_seismic_header_qa.md
│   └── claude_desktop_config_example.json
├── tests/
│   ├── test_las_tools.py
│   ├── test_dlis_tools.py
│   ├── test_segy_tools.py
│   ├── test_pump_card_tools.py
│   ├── test_path_validator.py
│   └── fixtures/                      # Tiny synthetic files for unit tests
├── evals/
│   ├── README.md
│   ├── scenarios/
│   │   ├── 01_well_log_qc.yaml
│   │   ├── 02_compare_wells.yaml
│   │   ├── 03_pump_card_diagnosis.yaml
│   │   └── 04_seismic_header_qa.yaml
│   ├── run_eval.py
│   └── results/
│       └── 2026-05-XX.md
├── docs/
│   ├── INSTALL.md
│   ├── DATA_PRIVACY.md                # Top-level prominent.
│   ├── SUPPORTED_FORMATS.md
│   ├── TOOLS_REFERENCE.md
│   ├── PROMPTS_REFERENCE.md
│   ├── EXAMPLES.md
│   ├── TROUBLESHOOTING.md
│   └── ARCHITECTURE.md
└── .github/
    └── workflows/
        ├── ci.yml
        └── release.yml                # PyPI on tag
```

## Configuration

User-level config in `~/.petromcp/config.json` or per-project `.petromcp.json`:

```json
{
  "allowed_paths": [
    "~/petroleum/wells",
    "~/petroleum/seismic",
    "/data/synthetic"
  ],
  "read_only": true,
  "max_file_size_mb": 100,
  "default_depth_units": "ft",
  "default_pressure_units": "psi",
  "cache_dir": "~/.petromcp/cache",
  "logging": {
    "enabled": true,
    "level": "info",
    "log_file": "~/.petromcp/access.log"
  }
}
```

The `allowed_paths` list is enforced strictly. A request to read a file outside any allowed path returns an error: `petromcp: path <X> is not in allowed_paths. Add it to ~/.petromcp/config.json or invoke with --temp-allow <path>`.

Logging is on by default. Users can audit what was accessed.

## Tool specifications, summarized

**`read_las_file(path)`**
Returns: well name, well operator (if present in header), depth range, depth units, list of curves with their units and ranges, total depth points, gap summary. Does NOT return raw curve data; that requires `read_las_curve`. Output is a few hundred tokens at most.

**`summarize_las_curves(path)`**
Returns: per-curve summary statistics (min, max, mean, stddev, gap percentage, expected vs. observed unit). Useful for quick QC.

**`read_las_curve(path, curve_name, depth_range=None)`**
Returns: depth array and value array, optionally subsetted by depth range. The default `depth_range=None` returns a downsampled view (every Nth point) capped at 500 samples; an explicit range can return all points within. This prevents accidental megabyte responses.

**`read_dlis_file(path)`**
Returns: list of logical files within the DLIS, frames per logical file, channels per frame, time range (if present). DLIS is more complex than LAS; the summary is necessarily denser.

**`list_dlis_channels(path)`**
Returns: detailed channel list with units, dimensions, and data types.

**`read_dlis_channel(path, channel_name, frame=None)`**
Returns: subsampled channel data with the same 500-sample default cap as LAS.

**`extract_segy_headers(path)`**
Returns: textual header (the EBCDIC-decoded one), binary header summary (sample interval, number of samples, format code), and trace count. Trace data not included.

**`parse_pump_card_csv(path)`**
Returns: pump configuration, time range, number of cycles, summary statistics on surface and pump cards, and a flag indicating whether the data appears to contain failure modes worth investigating (gas interference signature, fluid pound signature, etc.).

**`compare_well_logs(path_a, path_b)`**
Returns: which curves are common, which are unique to each, depth range overlap, unit consistency check, and a flag for any obvious issues.

**`convert_units(value, from_unit, to_unit)`**
Pure utility. ft/m, psi/kPa, bbl/m3, mD/m2, etc.

## Synthetic data generation

`examples/sample_data/generate.py` produces the sample files. Each file is generated from random seeds (controlled, reproducible). The script:

- Generates `synthetic_well_01.las` with curves: GR (gamma ray), RHOB (density), NPHI (neutron porosity), DT (sonic), Caliper. Depth range 5000-9000 ft, 0.5 ft sampling.
- Generates `synthetic_well_02.las` with overlapping but not identical curves, for the comparison demo.
- Generates `synthetic_well.dlis` using `dlisio.dlis.create` (or equivalent) with two channels.
- Generates `synthetic_seismic.sgy` with header-only structure (1000 traces, 4ms sample rate, EBCDIC header containing made-up survey metadata).
- Generates `synthetic_pump_card.csv` with 200 cycles of pump dynacard data, including 20 cycles with synthetic gas interference inserted.

The script's docstring emphasizes that this is synthetic and explains the data characteristics so users understand what the demos are showing.

## Evaluation methodology

Four scenarios. Each tests a realistic petroleum workflow.

**Scenario 1: Well log QC.**
User asks Claude to review a well log file. Claude should: identify the curves, flag any gaps, check unit consistency, note any out-of-range values. Reference: a hand-curated QC report. Score: did Claude flag every issue the reference flags? Did it raise false alarms?

**Scenario 2: Compare two wells.**
User asks Claude to compare two LAS files. Claude should: identify common curves, note the depth overlap, flag unit mismatches if any. Reference: a structured comparison report.

**Scenario 3: Pump card diagnosis.**
User asks Claude to look at a pump card CSV and identify any failure modes. Synthetic file has known failure modes inserted. Score: did Claude correctly classify the inserted failures?

**Scenario 4: Seismic header QA.**
User asks Claude to summarize a seismic survey. Claude should report: coordinates if present, sample rate, survey size, processing history (from textual header). Reference: a one-paragraph summary.

For each scenario, run with petromcp installed and without. Without petromcp, Claude is forced to ask the user for the data, or hallucinate. With petromcp, Claude reads the file directly. The contrast is the value demonstration.

Eval cost: minimal, because the eval is local. ~$2-5 in API tokens for a full run.

## CLI surface

```bash
# Install petromcp into Claude Desktop / Claude Code
petromcp install --client claude-desktop
petromcp install --client claude-code

# Initialize per-project config with sample paths
petromcp init

# Manually start the server (for debugging or non-Anthropic hosts)
petromcp serve

# Test a tool against a file
petromcp test read_las_file --path examples/sample_data/synthetic_well_01.las

# Generate sample data
petromcp generate-samples --output ~/petromcp-samples

# Show currently allowed paths
petromcp config show

# Add a path to the allowlist
petromcp config add-path ~/my-wells

# Uninstall
petromcp uninstall
```

## README structure

1. **Hero.** "petromcp lets Claude read your LAS, DLIS, SEG-Y, and pump card files directly." Animated GIF of a Claude Desktop session: user uploads a well log, asks "what's wrong with this log?", Claude reads it via petromcp and produces a QC report. One-line install.
2. **What this gives you.** Three sentences. The pain (LLMs can't read binary petroleum formats). The fix (an MCP server that wraps the open-source parsers). The result (you can have a conversation with your data).
3. **Quick start.** Install command, sample data download, three-command demo.
4. **Tool list.** Compact table.
5. **Privacy and safety.** Above-the-fold pointer to DATA_PRIVACY.md. Three sentences explaining the local-first, allowlist-default posture.
6. **Real example.** Walk-through of one scenario from `examples/walkthroughs/`. Show actual session transcript.
7. **Configuration.** Quick example, link to full reference.
8. **Roadmap.** v2 plans (WITSML, hosted version with OAuth, more formats).

Below the fold:
- Architecture
- Supported formats with version specifics
- FAQ (anticipated: "does this send my data to Anthropic?", "how do I add a new format?", "can I use it offline?")
- Acknowledgments (lasio, dlisio, segyio authors)
- Contributing
- License

## Launch playbook (different from the others)

The standard Show HN + r/ClaudeAI playbook will get this maybe 100 stars. The petroleum audience is elsewhere. Here is the channel-tuned approach:

**Day -7 to -3:**
- [ ] Repo polished. README has GIF. DATA_PRIVACY.md is solid.
- [ ] Sample data generator works and is documented.
- [ ] Eval results published.
- [ ] Reach out to known petroleum-AI people (Hoss Belyadi, Shahab Mohaghegh's circles, the Equinor dlisio team). Offer them an early look. A retweet from a known voice in petroleum data science is worth thousands of generic developer impressions.

**Day 0 (Tuesday-Thursday):**
- [ ] Show HN at 8 AM ET. The HN crowd will respect the technical novelty even though they aren't the primary user. Title: "Show HN: petromcp, MCP server for petroleum data formats (LAS, DLIS, SEG-Y, pump cards)."
- [ ] r/ClaudeAI cross-post. 50-200 stars likely from this.
- [ ] r/petroleumengineering post. Different framing: "I built an open-source tool that lets ChatGPT-style assistants read well logs directly. Free, local, MIT." Lead with the user benefit, not the tech.
- [ ] LinkedIn post. This is where petroleum engineers actually hang out professionally. Long-form, personal, framed as "I built this for a problem I kept hitting." Tag SPE-related contacts.
- [ ] Submit to SPE Connect community forum.

**Day 1-3:**
- [ ] Post in selected SPE technical sections (Petroleum Data-Driven Analytics is the obvious one).
- [ ] Submit a short to JPT Online ("Open-Source Tool of the Month" type slot, if one exists).
- [ ] Reach out to RigZone, Hart Energy, and Oil & Gas Journal with a compact pitch. Even a small mention drives meaningful traffic from this audience.

**Day 7+:**
- [ ] One walkthrough video per week. Real workflows: "QC a well log in 30 seconds with petromcp." Five-minute screencasts.
- [ ] If traction is real, consider a SPE Distinguished Lecturer pitch for a future cycle (this is a long-game move).

**Honest expected outcome:** 150-400 stars in the first week. 300-800 over six months. Numerical ceiling is real, but the audience is qualitatively different from a typical OSS launch. Many of these stars come from named operators and named professionals, which is more valuable per-star than anonymous developer stars.

## Risks and mitigations

**Risk 1: Petroleum operators are nervous about pointing a "Claude tool" at their data.**
*Mitigation:* DATA_PRIVACY.md is the lead document. The allowlist-default posture is non-negotiable. The first launch tweet leads with privacy, not features.

**Risk 2: Schlumberger or another large operator notices and asks awkward questions about your involvement, given your past employment.**
*Mitigation:* This is a real concern. The mitigation is twofold. First: every line of code in this project must be written from scratch using publicly documented libraries (lasio, dlisio, segyio). No internal SLB code, no internal SLB documentation, no work-product overlap. Second: when promoting, do not lead with "I'm a former Schlumberger engineer." Lead with the tool. Your experience informed the tool selection (you know which formats matter); it did not produce any of the code. If asked, be candid and concise.

**Risk 3: dlisio's API changes.**
*Mitigation:* Pin versions. CI runs against the latest published dlisio weekly to detect breaks early.

**Risk 4: Audience doesn't show up.**
*Mitigation:* If post-launch traffic is anemic, the LinkedIn + SPE channels are the recovery path. Patience. This audience moves slower than developer Twitter.

**Risk 5: Someone else ships a similar tool first.**
*Mitigation:* As of May 2026, no public petroleum-format MCP server exists with reasonable coverage. Window is open. Speed matters.

## Post-v0.1 roadmap

v0.1 (tag `0.1`, shipped 2026-05-07) covers LAS only: three tools, the QC prompt, the path allowlist, the synthetic generator, the eval, and Claude Desktop install. The remaining items below are sorted by *additivity* — Tier 1 cannot regress what shipped; later tiers introduce new code paths that need their own design + plan + execution cycle.

### Tier 1 — recommended v0.2 scope

Short, additive, tightens what v0.1 already does. Pure extensions to the existing LAS surface.

1. **`compare_well_logs(path_a, path_b) -> ComparisonReport`.** Pure LAS-on-LAS. Reports common curves, depth-overlap, unit-consistency check, obvious-issue flags. Pairs with eval scenario 02.
2. **`convert_units(value, from_unit, to_unit) -> float`.** Pure utility. ft/m, psi/kPa, bbl/m3, mD/m².
3. **`petromcp config show` and `petromcp config add-path`.** CLI subcommands so users do not have to hand-edit `~/.petromcp/config.json`.
4. **Bad-LAS fixture corpus.** A small set of malformed LAS files (missing `~Well`, comma-decimal locale, broken line endings, unicode in headers) plus tests that lock in graceful failure.
5. **Tighten `pyproject.toml` description.** Currently lists DLIS, SEG-Y, and pump cards alongside LAS. Same overpromise the README hero had. One-line fix.

### Tier 2 — additive, larger; each gets its own slice

6. **DLIS slice.** `read_dlis_file`, `list_dlis_channels`, `read_dlis_channel`. Same TDD pattern as LAS. Pin `dlisio`; CI-watch upstream.
7. **SEG-Y headers slice.** `extract_segy_headers`. Headers only; full traces remain out of scope per the v1 non-goals.
8. **Pump card slice.** `parse_pump_card_csv` + `diagnose_pump_card` prompt.
9. **Plotly resources.** `well_log_plot://` and `pump_card_plot://` URIs returning HTML payloads.

### Tier 3 — operational and launch readiness

10. **Cursor and Codex CLI install scripts** in the existing `petromcp install` subcommand.
11. **Eval scenarios 02 (compare wells), 03 (pump card), 04 (seismic header).**
12. **`.github/workflows/release.yml`** — PyPI publish on tag. Defer until DLIS lands.
13. **Weekly FastMCP-float CI job** to catch upstream breaks.
14. **Walkthrough markdowns** under `examples/walkthroughs/`. Backbone for the launch GIF.
15. **`--temp-allow <path>` CLI flag** for one-off reads without editing config.

## Stretch goals

1. WITSML support (real-time drilling data XML).
2. Streamable HTTP transport with OAuth, for organizations that want to host petromcp centrally.
3. Reservoir simulation output formats (Eclipse RST, etc.). Big project, separate effort.
4. Integrated Python notebook generator: a tool that emits a `.ipynb` file with the analysis Claude described in the conversation. Bridges chat workflow back into traditional engineering deliverables.
5. petromcp-bench: a small companion benchmark for petroleum-data-aware LLMs. Could be its own project.

## Out of scope for this spec

- Cloud-hosted version (v2).
- Reservoir simulation outputs.
- Real-time data feeds (WITSML, OPC-UA, etc.).
- Visualization frameworks beyond Plotly HTML.
- Auto-detection of proprietary data.
- Integration with PI, OSI, IP21, or other production data warehouses.

## Definition of done for v1

- [ ] All ten tools work against the synthetic sample data.
- [ ] Both prompts are functional and tested in Claude Desktop and Claude Code.
- [ ] Path allowlist is enforced. Tests verify denial of out-of-allowlist paths.
- [ ] Sample data generator is reproducible.
- [ ] All four eval scenarios pass with documented metrics.
- [ ] DATA_PRIVACY.md is solid, reviewed twice.
- [ ] README polished with GIF demo.
- [ ] Install scripts work for Claude Desktop, Claude Code, Cursor.
- [ ] Uninstall is clean.
- [ ] CI green.
- [ ] License in place (MIT).
- [ ] All docs cross-linked from the docs index.

When all boxes are checked, ship it. Be patient with the launch. The audience is real but they don't move fast.
