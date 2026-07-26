# Security policy

## Reporting a vulnerability

Report security issues through GitHub's private vulnerability reporting on
[the petromcp repository](https://github.com/ameyxd/petromcp/security/advisories/new).
Please do not open a public issue for a vulnerability.

Expect an acknowledgement within a week. If a fix is warranted, it ships in
a patch release with credit unless you prefer otherwise.

## Threat model

petromcp reads local files and hands their contents to an MCP host, which
in turn forwards them to a language-model provider. The security boundary
that matters is therefore **which files it can read**.

- The path allowlist is default-deny. A fresh install can read nothing.
- Every file-reading tool routes through `validate_path`, which resolves
  symlinks before comparing against the allowlist, so a symlink inside an
  allowed directory cannot reach outside it.
- There is no escape hatch, no environment-variable override, and no tool
  that mutates the allowlist at runtime. Changing it means editing
  `~/.petromcp/config.json` and restarting the host.
- petromcp opens no network connections. All tools are annotated
  `openWorldHint: false`.

Findings that would qualify as vulnerabilities include: any path that
reaches a file outside the allowlist, any code path that writes to or
deletes a user file, and any outbound network connection.

## What is not a vulnerability

- The MCP host forwarding tool results to a model provider. That is the
  host's behaviour and its privacy policy governs it. Read
  [docs/DATA_PRIVACY.md](docs/DATA_PRIVACY.md) before pointing petromcp at
  proprietary data.
- A malformed LAS file producing a wrong or degraded summary. That is a
  correctness bug — file it as a normal issue, ideally with the fixture.
- Anything reachable only by a user who already added the directory to
  their own allowlist.

## Supported versions

The latest release receives fixes. Older versions do not.
