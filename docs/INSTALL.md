# Installing petromcp

petromcp targets Claude Desktop in v1. Other hosts work if you point them at
the same `petromcp serve` command.

## Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for environment management
- Claude Desktop, current version
- macOS or Linux. Windows is not yet supported.

## Quick path (recommended)

The repo ships with a `Makefile` that wraps the common workflows.

    git clone https://github.com/<you>/petromcp
    cd petromcp
    make setup
    make install-claude

Restart Claude Desktop. petromcp's tools and the `qc_a_well_log` prompt
should appear in a new conversation.

`make help` lists every target.

## Manual path

If you prefer to drive `uv` directly:

    git clone https://github.com/<you>/petromcp
    cd petromcp
    uv sync
    uv run petromcp install --client claude-desktop

On macOS there is one extra step. uv 0.5.9 sets the `UF_HIDDEN` file flag on
editable-install `.pth` files, and Python 3.12+ silently skips hidden `.pth`
files, which causes `uv run petromcp` to fail with `ModuleNotFoundError`.
Clear the flag after every `uv sync`:

    chflags nohidden .venv/lib/python*/site-packages/*.pth

`make setup` does this for you. Use it unless you have a reason not to.

## Configure

Create `~/.petromcp/config.json`:

    {
      "allowed_paths": ["~/petroleum/wells"]
    }

petromcp refuses to read any file outside `allowed_paths`. This is the
deliberate default; see [DATA_PRIVACY.md](DATA_PRIVACY.md).

Optional fields:

    {
      "allowed_paths": ["~/petroleum/wells"],
      "logging": {
        "enabled": true,
        "log_file": "~/.petromcp/access.log"
      }
    }

Logging is on by default. Tool calls are recorded one per line as
`<timestamp> tool=<name> path=<resolved>`.

## Uninstall

    make uninstall-claude

removes petromcp from Claude Desktop's config. The Python package, your
config, and your logs are left in place; remove them manually if desired.

## Troubleshooting

- **Tool calls return "path is not in allowed_paths".** Add the directory to
  `allowed_paths` in `~/.petromcp/config.json` and restart Claude Desktop.
- **Claude Desktop does not see petromcp.** Confirm the config file at
  `~/Library/Application Support/Claude/claude_desktop_config.json` has an
  `mcpServers.petromcp` entry. Restart Claude Desktop after edits.
- **`uv run petromcp` fails with `ModuleNotFoundError` on macOS.** Run
  `make setup`, or apply the `chflags nohidden` workaround above.
- **Server fails to launch from Claude Desktop.** Run `make run` from a
  terminal; the error will be visible in stderr.
