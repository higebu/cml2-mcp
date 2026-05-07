# cml2-mcp recipes. Run `just` to list, `just <recipe>` to invoke.
set shell := ["bash", "-uc"]

default:
    @just --list

# Run ruff lint + format check.
check: lint fmt-check

# Run ruff lint.
lint:
    uv run ruff check

# Run ruff lint with --fix.
lint-fix:
    uv run ruff check --fix

# Format with ruff.
fmt:
    uv run ruff format

# Verify formatting without modifying files.
fmt-check:
    uv run ruff format --check

# Build sdist + wheel into dist/.
build:
    uv build

# Bump version, regenerate CHANGELOG, commit, and tag locally.
# Push manually with: git push origin main --tags
# level: major | minor | patch | alpha | beta | rc | post | dev
release level="patch":
    #!/usr/bin/env bash
    set -euo pipefail
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "error: working tree is dirty; commit or stash first" >&2
        exit 1
    fi
    if [[ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]]; then
        echo "error: not on main branch" >&2
        exit 1
    fi
    uv version --bump {{level}}
    new=$(uv version --short)
    uvx git-cliff --tag "v$new" --output CHANGELOG.md
    uv lock --quiet
    git add pyproject.toml CHANGELOG.md uv.lock
    git commit -m "chore: release v$new"
    git tag "v$new"
    echo
    echo "tagged v$new locally. push with:"
    echo "    git push origin main --tags"
