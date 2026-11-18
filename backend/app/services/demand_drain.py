"""Optional in-process drain of demand-driven sync jobs.

The standalone worker (``python -m worker.main``) is the primary consumer of the
jobs that searches enqueue. But in setups where only the API is running — local
dev, or a single-process deploy — those jobs would otherwise sit in ``PENDING``
forever, so the console would show "采集中…" and never any data.

This lets the API process a bounded batch of pending jobs *after* it has already
responded to the request. The job claim in ``jobs_repo.start`` is atomic, so this
can safely run alongside the standalone worker without double-processing (and
double-charging) any job. Cost stays guarded by the normal budget check inside
``run_pending`` and by ``max_jobs``.
"""

from __future__ import annotations

import logging
import sys

from app.core.config import REPO_ROOT, Settings, get_settings

logger = logging.getLogger("wechat_insight.demand_drain")


async def drain_demand_jobs(settings: Settings | None = None, max_jobs: int | None = None) -> int:
    """Process up to ``max_jobs`` pending jobs (defaults to the configured cap).

    Never raises: a background drain failing must not affect the request that
    triggered it. Returns the number of jobs processed (0 when disabled).
    """
    settings = settings or get_settings()
    if max_jobs is None:
        max_jobs = settings.on_demand_inline_drain_max_jobs
    if max_jobs <= 0:
        return 0

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from worker import engine
    except Exception:  # pragma: no cover - only when the worker package is absent
        logger.exception("inline demand drain unavailable: cannot import worker engine")
        return 0

    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        processed = await engine.run_pending(
            session,
            max_jobs=max_jobs,
            settings=settings,
        )
    except Exception:  # pragma: no cover - defensive; engine already swallows per-job errors
        logger.exception("inline demand drain failed")
        session.rollback()
        return 0
    finally:
        session.close()

    if processed:
        logger.info("inline demand drain processed %s job(s)", processed)
    return processed
