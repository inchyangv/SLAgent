"""Repo-root .env loader (single place for env management).

This project intentionally avoids heavy config frameworks for demo stability.
We load a single `.env` file from the repo root and inject variables into
`os.environ` without overriding already-set environment variables.

Supported syntax (minimal):
- `KEY=VALUE`
- optional `export KEY=VALUE`
- blank lines and `#` comments
- single/double quoted values
"""

from __future__ import annotations

import os
from pathlib import Path


def _strip_quotes(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
        return val[1:-1]
    return val


def _parse_env_line(line: str) -> tuple[str, str] | None:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None

    if raw.startswith("export "):
        raw = raw[len("export ") :].lstrip()

    if "=" not in raw:
        return None

    key, val = raw.split("=", 1)
    key = key.strip()
    if not key:
        return None

    # Remove inline comments if value is unquoted.
    v = val.strip()
    if v and v[0] not in ("'", '"') and " #" in v:
        v = v.split(" #", 1)[0].rstrip()
    if v and v[0] not in ("'", '"') and "\t#" in v:
        v = v.split("\t#", 1)[0].rstrip()

    return key, _strip_quotes(v)


def find_repo_root(start: Path) -> Path:
    """Ascend from start until we find a repo marker."""
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent

    for _ in range(12):
        if (cur / ".git").exists() or (cur / "PROJECT.md").exists() or (cur / "pyproject.toml").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve() if start.is_dir() else start.resolve().parent


def load_dotenv(path: Path, *, override: bool = False) -> bool:
    """Load dotenv file into os.environ.

    Returns True if the file existed and was read.
    """
    if not path.exists() or not path.is_file():
        return False

    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, val = parsed
        if not override and key in os.environ and os.environ[key] != "":
            continue
        os.environ[key] = val
    return True


def bootstrap_env(*, env_filename: str = ".env") -> Path | None:
    """Load repo-root `.env` once per process.

    Returns the loaded path, or None if not found.
    """
    if os.getenv("_SLA_PAY_ENV_BOOTSTRAPPED", "") == "true":
        return None

    here = Path(__file__).resolve()
    root = find_repo_root(here)
    env_path = root / env_filename
    if load_dotenv(env_path, override=False):
        os.environ["_SLA_PAY_ENV_BOOTSTRAPPED"] = "true"
        return env_path

    # Mark bootstrapped even if missing; avoids repeated filesystem scans.
    os.environ["_SLA_PAY_ENV_BOOTSTRAPPED"] = "true"
    return None

