"""Provider connectivity check (never prints secrets).

Usage (from backend/):
  PROVIDER_ORDER=xmedi,qovia \
  XMEDI_API_KEY=... QOVIA_BASE_URL=... QOVIA_API_KEY=... \
    python -m scripts.check_provider "科技"

By default Xmedi is the primary source and Qovia the fallback; this probes the
configured **failover chain** with a single billed call (primary first, switching
on failure). Flags:

  --provider NAME   probe one specific source only
  --all             probe every configured source individually (bills each)

Exits non-zero with a stable error code if the probe fails, so it can gate
deployments/CI when real credentials are configured.
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
from app.providers import registry  # noqa: E402
from app.providers.registry import get_provider  # noqa: E402


async def _probe(keyword: str, provider) -> bool:
    label = getattr(provider, "name", "?")
    try:
        page = await provider.search_accounts(keyword, page=1, page_size=1)
    except AppError as exc:
        print(f"FAIL provider={label} code={exc.code} message={exc.message}")
        return False

    print(f"OK provider={label} items={len(page.items)}")
    if page.items:
        sample = page.items[0]
        print(
            f"sample name={sample.name!r} provider={sample.provider!r} "
            f"provider_account_id={sample.provider_account_id!r}"
        )
    return True


async def run(keyword: str, provider_name: str | None, probe_all: bool) -> int:
    if provider_name:
        return 0 if await _probe(keyword, get_provider(provider_name)) else 2

    if probe_all:
        names = registry.configured_providers()
        if not names:
            print("FAIL no configured providers")
            return 2
        ok = True
        for name in names:
            if not await _probe(keyword, get_provider(name)):
                ok = False
        return 0 if ok else 2

    chain = get_provider()
    members = getattr(chain, "providers", None)
    if members:
        print(f"chain={[p.name for p in members]}")
    return 0 if await _probe(keyword, chain) else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Check provider connectivity")
    parser.add_argument("keyword", nargs="?", default="科技")
    parser.add_argument("--provider", default=None)
    parser.add_argument(
        "--all",
        action="store_true",
        help="probe every configured source individually (bills each)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.keyword, args.provider, args.all)))


if __name__ == "__main__":
    main()
