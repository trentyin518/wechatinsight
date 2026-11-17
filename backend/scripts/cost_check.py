"""Post-deploy cost self-check: confirm nothing is calling the paid API on its own.

Prints the effective cost flags (COLLECTION_ENABLED / SEARCH_RETRY_ENABLED),
budgets, recent background activity and the live provider balance, then gives a
verdict. Exit code is non-zero when calls happened during the window while both
background switches are OFF — a sign that a stray/remote worker is still running.

Usage (from backend/):
  python -m scripts.cost_check                 # 10-minute window
  python -m scripts.cost_check --window 30     # 30-minute window
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from sqlalchemy import func, select  # noqa: E402

    from app.core.config import get_settings  # noqa: E402
    from app.db.models import ApiUsageLog, SearchRetryQueue, SyncJob  # noqa: E402
    from app.db.session import SessionLocal  # noqa: E402
    from app.providers.registry import get_provider  # noqa: E402
except ModuleNotFoundError as exc:  # wrong interpreter / not the project venv
    print(f"缺少依赖或缺包：{exc.name}")
    print("请用项目虚拟环境运行（不要在 backend/ 之外用系统 python）：")
    print("  cd backend && .venv/bin/python -m scripts.cost_check --window 15")
    print("  # 或")
    print("  cd backend && .venv/bin/python scripts/cost_check.py --window 15")
    raise SystemExit(2) from exc


async def _balance() -> str:
    try:
        provider = get_provider()
        get_billing = getattr(provider, "get_billing", None)
        if not callable(get_billing):
            return "n/a (provider has no billing)"
        billing = await get_billing()
        if not billing:
            return "n/a (unavailable)"
        return f"{billing.get('balance_usd')} ({billing.get('plan')})"
    except Exception as exc:  # balance is best-effort
        return f"n/a ({type(exc).__name__})"


async def run(window_minutes: int) -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=window_minutes)

    session = SessionLocal()
    try:
        window_calls = session.scalar(
            select(func.count()).select_from(ApiUsageLog).where(
                ApiUsageLog.request_time >= since
            )
        )
        # Calls carrying a job_id come from the worker/sync pipeline, not from a
        # user's live search — these are the "background" calls we must not see
        # when the switches are off.
        window_job_calls = session.scalar(
            select(func.count()).select_from(ApiUsageLog).where(
                ApiUsageLog.request_time >= since,
                ApiUsageLog.job_id.is_not(None),
            )
        )
        window_charged = session.scalar(
            select(func.coalesce(func.sum(ApiUsageLog.estimated_cost), 0.0)).where(
                ApiUsageLog.request_time >= since
            )
        )
        window_by_endpoint = session.execute(
            select(
                ApiUsageLog.endpoint,
                func.count(),
                func.coalesce(func.sum(ApiUsageLog.estimated_cost), 0.0),
            )
            .where(ApiUsageLog.request_time >= since)
            .group_by(ApiUsageLog.endpoint)
            .order_by(func.count().desc())
            .limit(6)
        ).all()
        max_time = session.scalar(select(func.max(ApiUsageLog.request_time)))
        active_jobs = session.scalar(
            select(func.count()).select_from(SyncJob).where(
                SyncJob.status.in_(["PENDING", "RUNNING", "RETRY"])
            )
        )
        pending_retries = session.scalar(
            select(func.count()).select_from(SearchRetryQueue).where(
                SearchRetryQueue.status == "pending"
            )
        )
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_calls = session.scalar(
            select(func.count()).select_from(ApiUsageLog).where(
                ApiUsageLog.request_time >= today_start
            )
        )
    finally:
        session.close()

    balance = await _balance()

    print("== 成本自检 ==")
    print(f"  provider                : {settings.default_provider}")
    print(f"  COLLECTION_ENABLED      : {settings.collection_enabled}")
    print(f"  SEARCH_RETRY_ENABLED    : {settings.search_retry_enabled}")
    print(f"  ALLOW_COLD_START_SEARCH : {settings.allow_cold_start_search}  (用户搜索未命中才实时调用)")
    print(f"  日/月预算                : ${settings.daily_budget_usd} / ${settings.monthly_budget_usd}")
    print(f"  数据源余额               : {balance}")
    print(f"  近 {window_minutes} 分钟调用        : {window_calls}  (其中任务/后台 {window_job_calls})")
    print(f"  近 {window_minutes} 分钟估算扣费     : ${round(float(window_charged or 0.0), 4)}")
    for endpoint, n, cost in window_by_endpoint:
        print(f"      - {endpoint:<20} n={n:<4} cost=${round(float(cost), 4)}")
    print(f"  今日调用                 : {today_calls}")
    print(f"  最近一次调用时间          : {max_time}")
    print(f"  活跃任务(P/R/RETRY)      : {active_jobs}")
    print(f"  待处理搜索重试            : {pending_retries}")

    background_on = settings.collection_enabled or settings.search_retry_enabled
    if window_job_calls and not background_on:
        print(
            "\nWARNING: 后台开关均为关，但检测到近期【任务/后台】调用 —— 很可能是"
            "线上（未重部署的）worker 仍在运行。请在服务器执行："
        )
        print("         sudo systemctl stop wechatinsight-worker && sudo systemctl disable wechatinsight-worker")
        return 3
    if not window_calls and not background_on:
        print("\nOK: 后台开关均为关，近期无任何调用（省钱模式）。")
        return 0
    if window_calls and background_on:
        print("\nNOTE: 后台已开启且有调用，请在 /admin/usage 持续关注消耗。")
        return 0
    print("\nOK: 后台开启但近期无调用。")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="WeChat Insight cost self-check")
    parser.add_argument("--window", type=int, default=10, help="观察窗口（分钟），默认 10")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.window)))


if __name__ == "__main__":
    main()
