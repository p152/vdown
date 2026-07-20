import logging

from bot.services.jobs import clear_active, get_active_task_id
from bot.services.vidbee import VidBeeClient, VidBeeError, humanize_error

logger = logging.getLogger(__name__)

vidbee = VidBeeClient()


async def cancel_active_download(user_id: int) -> str:
    task_id = await get_active_task_id(user_id)

    if not task_id or task_id == "pending":
        await clear_active(user_id)
        return "ℹ️ Нет активной загрузки."

    try:
        cancelled = await vidbee.cancel_download(task_id)
    except VidBeeError as exc:
        return f"❌ {humanize_error(exc.category, str(exc))}"

    await clear_active(user_id)

    if cancelled:
        return "✅ Загрузка отменена."
    return "ℹ️ Загрузка уже завершена или не найдена."
