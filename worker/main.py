"""Worker entrypoint.

Usage:
  python -m worker.main --once          # run one enqueue+process cycle, then exit
  python -m worker.main                # start interval scheduler (default 300s)
  python -m worker.main --interval 60  # custom interval
"""

from __future__ import annotations

import argparse
import logging
import signal
import time

from worker import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="WeChat Insight collection worker")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--interval", type=int, default=300, help="scheduler interval seconds")
    args = parser.parse_args()

    if args.once:
        result = scheduler.run_cycle_sync()
        logging.getLogger("wechat_insight.worker").info("cycle result: %s", result)
        return

    sched = scheduler.build_scheduler(interval_seconds=args.interval)
    sched.start()
    logging.getLogger("wechat_insight.worker").info(
        "scheduler started (interval=%ss). Ctrl+C to stop.", args.interval
    )

    stop = {"flag": False}

    def _handle(_signum, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    try:
        while not stop["flag"]:
            time.sleep(1)
    finally:
        sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
