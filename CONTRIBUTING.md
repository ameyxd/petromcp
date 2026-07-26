# Contributing

## Setup

    git clone https://github.com/ameyxd/petromcp
    cd petromcp
    make setup

On macOS, always drive the project through `make`, not raw `uv run`. uv sets
the `UF_HIDDEN` flag on editable-install `.pth` files and Python 3.12+
silently skips hidden ones, which breaks the `petromcp` entry point. The
`Makefile` clears the flag and passes `--no-sync` so it stays cleared.

## Before opening a pull request

    make check

That runs `ruff`, `pyright`, and `pytest`. CI runs the same three plus the
QC eval, on Python 3.10 and 3.12.

## Conventions

- Python 3.12 for development; 3.10 is the supported floor and CI tests it.
- TDD where it pays: parsers, validators, summarizers. Write the failing
  test first. Wiring code (FastMCP registration, CLI) is smoke-tested.
- Pydantic models are frozen and contain no I/O.
- Tools never read files directly. Every read goes through
  `utils/path_validator.validate_path`. Do not bypass the allowlist in
  tests by monkeypatching the validator — use the real validator with a
  `tmp_path` allowlist.
- Outputs are token-budgeted. Anything that can return an unbounded array
  needs a cap and a `downsampled` flag.
- Commit on every green test. Small commits beat big ones.

## Adding a malformed-file fixture

The bad-LAS corpus under `tests/fixtures/bad_las/` exists because
real-world LAS files are frequently broken. If you hit a file that breaks
petromcp, the most useful contribution is a minimal fixture reproducing it
plus a test asserting the degraded behaviour you think is right.

Every file-reading tool must survive every fixture. A crash on a malformed
file is a bug even when a wrong answer would be acceptable.

## Scope

`SPEC_petromcp.md` has a non-goals list. It is real — read it before
proposing a feature. Format support lands in vertical slices (one format,
end to end, with tools, docs, tests, and an eval) rather than as partial
support for several formats at once.

## Security

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).
