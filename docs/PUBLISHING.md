# Publishing petromcp

Three destinations, in dependency order. PyPI first — both directories point
at the package, so publishing them before it exists yields listings whose
install instructions fail.

Everything below needs credentials, so these are commands to run yourself,
not steps to automate.

## 0. Build and check the artefacts

    make release-artifacts

That runs lint, types, and tests, then writes three files into `dist/`:

| File | Destination |
|------|-------------|
| `petroleum_mcp-<version>-py3-none-any.whl` | PyPI |
| `petroleum_mcp-<version>.tar.gz` | PyPI |
| `petromcp-<version>.mcpb` | Smithery |

## 1. PyPI

Pass the token explicitly. Do not answer uv's interactive username/password
prompt:

    UV_PUBLISH_TOKEN=$(python3 -c "import getpass;print(getpass.getpass('PyPI token: '))") \
      uv publish dist/petroleum_mcp-*.whl dist/petroleum_mcp-*.tar.gz

That reads the token without echoing it and without leaving it in shell
history or the environment.

**Two failure modes worth knowing, both of which return a bare 403:**

*"Username/Password authentication is no longer supported."* — uv prompted
for a username and a password, and got a real username. PyPI dropped
password auth entirely. If you use the prompt rather than the token flag,
the username must be the literal string `__token__` and the password the
whole token including its `pypi-` prefix. Using `--token` or
`UV_PUBLISH_TOKEN` sets both correctly for you.

*"Invalid or non-existent authentication information."* — usually a
pypi.org token aimed at TestPyPI, which is a separate site with separate
accounts and tokens. See below.

**The first upload of a new project needs an account-scoped token**, from
<https://pypi.org/manage/account/token/> with scope "Entire account". A
project-scoped token cannot work until the project exists, because there is
nothing yet to scope it to. Narrow it to project scope after the first
release.

Verify with a clean cache before moving on — everything downstream depends
on this working:

    uvx --no-cache petroleum-mcp@<version> --help

### On TestPyPI

Skip it. TestPyPI is a wholly separate site: separate account, separate
tokens, separate package index. A pypi.org token 403s against it, which is
the confusing failure mode most people hit. It also cannot resolve
petromcp's dependencies without
`--index-strategy unsafe-best-match`, because they are not mirrored there.

The thing TestPyPI would catch — a wheel that does not install or run — is
better caught locally, and more thoroughly:

    uv build
    uv venv --python 3.10 /tmp/probe && uv pip install --python /tmp/probe/bin/python dist/petroleum_mcp-*.whl
    /tmp/probe/bin/petromcp --help

Then exercise the real stdio path with `uvx --from ./dist/petroleum_mcp-*.whl
petromcp serve --allow-path <dir>` and confirm both an allowed read and a
refused one. That is a stronger check than a TestPyPI round trip.

## 2. Glama

Glama crawls public GitHub repos on its own, so the listing appears without
being submitted. `glama.json` in the repo root claims it:

```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["ameyxd"]
}
```

1. Push `glama.json` to `main`.
2. Sign in at <https://glama.ai/> with the GitHub account named in
   `maintainers`.
3. Find the petromcp listing and run the claim flow.

Claiming unlocks editing the name and description, configuring a Docker
image, usage reports, and review notifications. Re-run the claim flow after
any later edit to `glama.json`.

## 3. Smithery

**Do not publish here until step 1 is done and verified.** The bundle
launches `uvx petroleum-mcp@<version>`; published against a version that is not
on PyPI, every install fails with a package-not-found error. A listing that
fails on first try is worse than no listing.

petromcp is a local stdio server, so the hosted-URL path does not apply: a
container in Smithery's cloud cannot read LAS files on the user's disk, and
the path allowlist is the entire privacy posture. The local MCPB bundle is
the correct route.

`auth login` needs a real terminal — it does nothing useful when run
headless.

    npx -y @smithery/cli@latest auth login
    npx -y @smithery/cli@latest mcp publish dist/petromcp-<version>.mcpb -n ameyxd/petromcp

Then open the server's **Settings → Verification** page and complete the
vendor verification checks.

### Two uvx traps, both verified the hard way

`uvx <name>==<version>` is a **parse error** — uvx reads the first argument as
a command name, and `==` is not legal there. The pinned form is
`uvx <name>@<version>`.

`uvx petroleum-mcp` only works because the package declares a console script
named `petroleum-mcp` alongside `petromcp` (see `[project.scripts]`). uvx runs
the executable whose name matches the package, and the distribution name and
the historical script name differ here. Drop that alias and every install
instruction in the README breaks with "executable not found".
`tests/test_cli.py::TestConsoleScripts` guards it.

When verifying a release, run the command the docs actually give, character for
character. Testing `uvx --from ./dist/*.whl petromcp serve` proves that
invocation works and says nothing about the one users will paste.

### What is in the bundle

`dist/petromcp-<version>.mcpb` is about 4KB — a manifest, the README, and the
licence. It does not vendor Python dependencies. It launches:

    uvx petroleum-mcp@<version> serve --allow-path <directories the user picked>

Vendoring was tried and rejected on evidence. numpy, pydantic-core and 27
other extension modules ship wheels tagged for one exact CPython minor
(`_pydantic_core.cpython-310-darwin.so`), so a bundle resolved against 3.10
imports fine on 3.10 and raises `ModuleNotFoundError` on 3.12. It could not
honestly declare `runtimes.python: ">=3.10"`. Delegating to uv moves
interpreter and dependency resolution onto the machine that runs the server.

The cost is that **uv must be on the user's PATH**. That is already
petromcp's documented prerequisite and the manifest's description says so,
but it is the one thing to revisit if install failures show up in Smithery's
logs. The fallback is a self-contained `server.type: "binary"` bundle with an
embedded interpreter, at roughly 60-100MB per platform.

## 4. Official MCP registry (optional)

`server.json` in the repo root is ready for it. This is the upstream feed
several directories read, so listing here improves reach beyond the two
above.

    npx -y @modelcontextprotocol/publisher login github
    npx -y @modelcontextprotocol/publisher publish

The namespace `io.github.ameyxd/petromcp` is proven by authenticating as
that GitHub account.

## Release checklist

Version appears in five places. `make bundle` fails loudly if the manifest
disagrees with `pyproject.toml`, and a test fails if `__init__.py` drifts,
but `server.json` is checked by neither.

- [ ] `pyproject.toml` `version`
- [ ] `packaging/mcpb/manifest.json` `version` **and** the `petroleum-mcp@<version>` pin in `args`
- [ ] `server.json` `version` and `packages[0].version`
- [ ] `CHANGELOG.md` has an entry
- [ ] `make release-artifacts` passes
- [ ] tag pushed (no `v` prefix): `git tag <version> && git push origin <version>`
- [ ] PyPI published and `uvx --no-cache petroleum-mcp@<version> --help` works
- [ ] Smithery bundle published
- [ ] Glama claim re-run if `glama.json` changed
