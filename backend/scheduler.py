from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.config import JOB_INTERVAL_HOURS

log = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _run_job():
    from backend.services.matching import run_matching_job
    try:
        await run_matching_job()
    except Exception:
        log.exception("Matching job failed")


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_job,
        trigger="interval",
        hours=JOB_INTERVAL_HOURS,
        id="matching_job",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.start()
    log.info("Scheduler started (interval: %dh)", JOB_INTERVAL_HOURS)


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
