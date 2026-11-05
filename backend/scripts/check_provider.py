"""Provider connectivity check (never prints secrets).

Usage (from backend/):
  DEFAULT_PROVIDER=qovia QOVIA_BASE_URL=... QOVIA_API_KEY=... \
    python -m scripts.check_provider "科技"

Exits non-zero with a stable error code if the provider is unreachable, so it
can gate deployments/CI when real credentials are configured.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.core.errors import AppError  # noqa: E402
from app.providers.registry import get_provider  # noqa: E402


async def run(keyword: str, provider_name: str | None) -> int:
    provider = get_provider(provider_name)
    try:
        page = await provider.search_accounts(keyword, page=1, page_size=1)
    except AppError as exc:
        print(f"FAIL provider={provider.name} code={exc.code} message={exc.message}")
        return 2

    print(f"OK provider={provider.name} items={len(page.items)}")
    if page.items:
        sample = page.items[0]
        print(f"sample name={sample.name!r} provider_account_id={sample.provider_account_id!r}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check provider connectivity")
    parser.add_argument("keyword", nargs="?", default="科技")
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.keyword, args.provider)))


if __name__ == "__main__":
    main()
