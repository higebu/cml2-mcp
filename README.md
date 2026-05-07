# cml2-mcp

Thin MCP server for Cisco CML2.

It deliberately avoids mirroring the CML API as typed (Pydantic) tools — every
prior generation that did so broke when the controller shipped a schema change.
Instead this server exposes only:

- `cml_openapi(refresh=False)` — fetch CML's live `openapi.json` (cached 24 h).
- `cml_api(method, path, body=None)` — generic authenticated REST call after
  `/api/v0`. Re-authenticates and retries once on HTTP 401.
- Resource `cml://openapi.json` — same content as `cml_openapi()`.

The model is expected to read the OpenAPI spec first and then craft calls.

## Configuration

Required environment:

| Var             | Example                          |
| --------------- | -------------------------------- |
| `CML_URL`       | `https://cml.example.net/`       |
| `CML_USERNAME`  | `admin`                          |
| `CML_PASSWORD`  | `…`                              |

Optional:

- `CML_VERIFY_SSL=true` — verify TLS (default: off; CML often uses self-signed certs).
- `CML_CACHE_DIR` — token / openapi cache directory (default: `~/.cache/cml/`).

The token is written to `$CML_CACHE_DIR/token` with mode `0600`.

## Running

With [uv](https://docs.astral.sh/uv/) directly from the source tree:

```sh
uv run cml2-mcp
```

After publishing to PyPI (or via `uv tool install .`):

```sh
uvx cml2-mcp
```

## Claude Desktop / Claude Code registration

Wrap the command so the password is fetched from a secure store rather than
appearing in plain text. Example with macOS Keychain:

```json
{
  "mcpServers": {
    "cml2": {
      "command": "sh",
      "args": [
        "-c",
        "CML_PASSWORD=$(security find-generic-password -a <account> -s <service> -w) exec uvx cml2-mcp"
      ],
      "env": {
        "CML_URL": "https://cml.example.net/",
        "CML_USERNAME": "admin"
      }
    }
  }
}
```

For Claude Code:

```sh
claude mcp add cml2 -- sh -c 'CML_PASSWORD=$(security find-generic-password -a <account> -s <service> -w) exec uvx cml2-mcp'
```

(Set `CML_URL` / `CML_USERNAME` in the same env or via `claude mcp add ... -e KEY=VAL`.)
