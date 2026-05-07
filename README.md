# petromcp

An MCP server that lets Claude read your LAS well log files directly.
Local-first. Synthetic data only by default. DLIS, SEG-Y, and pump card
support coming next.

## What this gives you

LLM hosts cannot read binary or semi-structured petroleum formats. petromcp
wraps the established open-source parsers — `lasio` for v0.1, with `dlisio`
and `segyio` queued for the next slices — and exposes them as MCP tools, so
you can have a conversation with your data instead of copy-pasting curve
values into chat.

## Privacy first

petromcp runs on your machine. It refuses to read any file outside an
explicit allowlist. There is no telemetry, no phone-home, no automatic
updates. See [DATA_PRIVACY.md](docs/DATA_PRIVACY.md) before pointing it at
real data.

## Quick start

    git clone https://github.com/<you>/petromcp
    cd petromcp
    make setup
    make install-claude

Then create `~/.petromcp/config.json`:

    {
      "allowed_paths": ["~/petroleum/wells"]
    }

Restart Claude Desktop. Ask: "what's wrong with this well log?" and point
it at a `.las` file inside that directory.

## Try it without your own data

If you don't have a LAS file handy, generate the synthetic sample first:

    make generate

This writes `examples/sample_data/synthetic_well_01.las` (gitignored,
reproducible from a fixed seed). Point your `allowed_paths` at
`examples/sample_data` instead of `~/petroleum/wells`, restart Claude
Desktop, and ask it to QC the file. The generator deliberately inserts a
small RHOB gap so the QC has something to flag.

## Tools (LAS, v0.1)

| Tool                    | What it does                                       |
|-------------------------|----------------------------------------------------|
| `read_las_file`         | Header-level summary of a LAS file                 |
| `summarize_las_curves`  | Per-curve min, max, mean, stddev, gap percentage   |
| `read_las_curve`        | Depths and values for one curve, with sampling cap |
| `qc_a_well_log` prompt  | Walks Claude through a standard QC pass            |

DLIS, SEG-Y, and pump card support land in subsequent releases.

## Status

v0.1 ships the LAS slice. The remaining formats are tracked in
[SPEC_petromcp.md](SPEC_petromcp.md). The non-goals list there is real;
read it before filing feature requests.

## License

MIT.
