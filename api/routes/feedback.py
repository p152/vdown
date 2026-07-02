from fastapi import APIRouter, Depends

from api.deps import require_admin
from bot.services.feedback import list_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(require_admin)])


@router.get("")
async def get_feedback(limit: int = 20):
    items = await list_feedback(limit=limit)
    return items
