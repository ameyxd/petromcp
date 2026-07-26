# petromcp

Read well logs with Claude without the data ever leaving your machine.

petromcp is an MCP server for petroleum data formats, built for teams whose
files legally cannot be uploaded to a cloud service. No telemetry, no
phone-home, no automatic updates, and a default-deny path allowlist that
refuses to open anything you have not explicitly permitted. LAS today; DLIS,
SEG-Y, and pump cards next.

If you can upload your data somewhere, you have more options than this. If you
can't, this was written for you.

## What this gives you

LLM hosts cannot read binary or semi-structured petroleum formats. petromcp
wraps the established open-source parsers — `lasio` today, with `dlisio`
and `segyio` queued for the next slices — and exposes them as MCP tools, so
you can have a conversation with your data instead of copy-pasting curve
values into chat.

## What "local-first" means here, concretely

Not a posture. Four things you can verify in the source:

- **Default deny.** A fresh install can read nothing. Access is granted per
  directory, and every tool routes through one validator that resolves
  symlinks before checking, so a link inside an allowed directory cannot
  reach outside it. There is no environment variable that widens the
  allowlist and no tool that changes it at runtime.
- **No network, declared.** petromcp opens no outbound connections. All five
  tools ship `openWorldHint: false` and `readOnlyHint: true`, so your host
  can verify that claim rather than take it.
- **An audit trail.** Every tool call is logged with a timestamp, the tool
  name, and the resolved path.
- **Bounded output.** Curve reads are capped and report `downsampled` and
  `original_count`, so a 20,000-point log cannot silently dump into a
  context window.

The threat model, and what does *not* count as a vulnerability, are in
[SECURITY.md](SECURITY.md). Read
[docs/DATA_PRIVACY.md](docs/DATA_PRIVACY.md) before pointing this at real
data — it is authoritative, and if the code contradicts it the code is the
bug.

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

Add petromcp to your MCP host's config — no clone, no build:

```json
{
  "mcpServers": {
    "petromcp": {
      "command": "uvx",
      "args": ["petroleum-mcp", "serve"]
    }
  }
}
```

On macOS that file is
`~/Library/Application Support/Claude/claude_desktop_config.json`. Restart
the host afterwards. macOS notes and troubleshooting:
[docs/INSTALL.md](docs/INSTALL.md).

To work on petromcp rather than just use it:

    git clone https://github.com/ameyxd/petromcp
    cd petromcp
    make setup
    make install-claude

## Configure

By default petromcp can read nothing. Tell it which directories are fair
game:

    uvx petroleum-mcp config init
    uvx petroleum-mcp config add-path ~/petroleum/wells

Or, if you want to try it without your own data, generate the synthetic
sample from a checkout and allowlist that:

    make generate
    uvx petroleum-mcp config add-path "$(pwd)/examples/sample_data"

Restart your MCP host after editing the allowlist — it is read once at
startup.

## Use

Open a new conversation and ask, in plain language:

    What's wrong with this well log? /path/to/well.las
    Compare these two wells: /path/to/A.las and /path/to/B.las
    Convert 1500 psi to kPa.

Claude picks the right tool, reads the file through petromcp, and answers.

## Tools

| Tool                    | What it does                                          |
|-------------------------|-------------------------------------------------------|
| `read_las_file`         | Header-level summary of a LAS file                    |
| `summarize_las_curves`  | Per-curve min, max, mean, stddev, gap percentage      |
| `read_las_curve`        | Depths and values for one curve, with sampling cap    |
| `compare_well_logs`     | Common curves, depth overlap, unit consistency, flags |
| `convert_units`         | ft<->m, psi<->kPa, psi<->bar, bbl<->m3, degF<->degC, mD<->m2 |
| `list_supported_units`  | Every convertible pair with its physical quantity      |
| `qc_a_well_log` prompt  | Walks Claude through a standard QC pass               |

Every tool is read-only and opens no network connection, and declares that
in its MCP annotations. Full reference:
[docs/TOOLS_REFERENCE.md](docs/TOOLS_REFERENCE.md).

DLIS, SEG-Y, and pump card support land in subsequent releases.

## Status

v0.5 ships the LAS slice, a comparison tool, a units utility, and
config-management CLI subcommands. The remaining formats are tracked in
[SPEC_petromcp.md](SPEC_petromcp.md). The non-goals list there is real;
read it before filing feature requests.

Release history: [CHANGELOG.md](CHANGELOG.md). Security policy and threat
model: [SECURITY.md](SECURITY.md).

## License

MIT.

---

Built by [Amey Ambade](https://heyamey.com). I write about AI systems in
industries where the data can't leave the building, at
[writing.heyamey.com](https://writing.heyamey.com).
