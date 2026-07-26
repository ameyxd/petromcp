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
| `petromcp-<version>-py3-none-any.whl` | PyPI |
| `petromcp-<version>.tar.gz` | PyPI |
| `petromcp-<version>.mcpb` | Smithery |

## 1. PyPI

Publish to TestPyPI first and install from it — a broken `uvx petromcp` is
visible on both directory listings the moment they index you.

    uv publish --publish-url https://test.pypi.org/legacy/ dist/petromcp-*.whl dist/petromcp-*.tar.gz
    uvx --index-url https://test.pypi.org/simple/ --index-strategy unsafe-best-match petromcp==<version> --help

Then the real thing:

    uv publish dist/petromcp-*.whl dist/petromcp-*.tar.gz

`uv publish` prompts for a token, or reads `UV_PUBLISH_TOKEN`. Generate a
project-scoped token at <https://pypi.org/manage/account/token/>.

Verify with a clean cache before moving on:

    uvx --no-cache petromcp==<version> --help

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

petromcp is a local stdio server, so the hosted-URL path does not apply: a
container in Smithery's cloud cannot read LAS files on the user's disk, and
the path allowlist is the entire privacy posture. The local MCPB bundle is
the correct route.

    npx -y @smithery/cli login
    npx -y @smithery/cli mcp publish dist/petromcp-<version>.mcpb -n ameyxd/petromcp

Then open the server's **Settings → Verification** page and complete the
vendor verification checks.

### What is in the bundle

`dist/petromcp-<version>.mcpb` is about 4KB — a manifest, the README, and the
licence. It does not vendor Python dependencies. It launches:

    uvx petromcp==<version> serve --allow-path <directories the user picked>

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
- [ ] `packaging/mcpb/manifest.json` `version` **and** the `petromcp==<version>` pin in `args`
- [ ] `server.json` `version` and `packages[0].version`
- [ ] `CHANGELOG.md` has an entry
- [ ] `make release-artifacts` passes
- [ ] tag pushed (no `v` prefix): `git tag <version> && git push origin <version>`
- [ ] PyPI published and `uvx --no-cache petromcp==<version> --help` works
- [ ] Smithery bundle published
- [ ] Glama claim re-run if `glama.json` changed
