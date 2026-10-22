from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.config import EMBEDDING_VERSION
from backend.models import User, PaperFeedback, PaperResearcherMatch
from backend.schemas import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
async def submit_feedback(
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(PaperFeedback).where(
            PaperFeedback.user_id == current_user.id,
            PaperFeedback.paper_openalex_id == body.paper_openalex_id,
            PaperFeedback.researcher_id == body.researcher_id,
        )
    )

    if body.verdict is None:
        if existing:
            await db.delete(existing)
            await db.commit()
        return {"status": "ok"}

    # Snapshot of the match the user saw, so feedback can be tied to a version, score and rank
    shown = await db.get(PaperResearcherMatch, (body.paper_openalex_id, body.researcher_id, EMBEDDING_VERSION))
    answer = {
        "verdict": body.verdict,
        "reason": body.reason if body.verdict != "yes" else None,
        "embedding_version": EMBEDDING_VERSION if shown else None,
        "score": shown.score if shown else None,
        "rank": shown.rank if shown else None,
    }

    if existing:
        for key, value in answer.items():
            setattr(existing, key, value)
    else:
        db.add(PaperFeedback(
            user_id=current_user.id,
            paper_openalex_id=body.paper_openalex_id,
            researcher_id=body.researcher_id,
            **answer,
        ))

    await db.commit()
    return {"status": "ok"}
