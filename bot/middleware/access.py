import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.access import is_admin
from bot.services.access_store import is_chat_allowed
from bot.states.admin import AdminStates
from bot.states.feedback import FeedbackStates

logger = logging.getLogger(__name__)

PUBLIC_COMMANDS = frozenset({"/start", "/help", "/feedback", "/bug", "/cancel"})

FSM_EXEMPT_STATES = frozenset({
    FeedbackStates.waiting_message.state,
    AdminStates.waiting_user_id.state,
    AdminStates.waiting_group_id.state,
})


def _extract_command(text: str | None) -> str | None:
    if not text or not text.startswith("/"):
        return None
    command = text.split()[0].split("@")[0].lower()
    return command


def _is_public_command(text: str | None) -> bool:
    command = _extract_command(text)
    return command in PUBLIC_COMMANDS if command else False


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        chat_id: int | None = None
        text: str | None = None

        if isinstance(event, Message):
            if not event.from_user:
                return await handler(event, data)
            user_id = event.from_user.id
            chat_id = event.chat.id
            text = event.text or event.caption
        elif isinstance(event, CallbackQuery):
            if not event.from_user or not event.message:
                return await handler(event, data)
            user_id = event.from_user.id
            chat_id = event.message.chat.id
        else:
            return await handler(event, data)

        if user_id is None or chat_id is None:
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state:
            current_state = await state.get_state()
            if current_state in FSM_EXEMPT_STATES:
                return await handler(event, data)

        if is_admin(user_id):
            return await handler(event, data)

        if isinstance(event, Message) and _is_public_command(text):
            return await handler(event, data)

        if await is_chat_allowed(chat_id, user_id):
            return await handler(event, data)

        logger.info("Access denied for user %s in chat %s", user_id, chat_id)

        if isinstance(event, Message):
            await event.answer(
                "🚫 У вас нет доступа к этому боту.\n\n"
                "Обратитесь к администратору или отправьте /feedback"
            )
        elif isinstance(event, CallbackQuery):
            await event.answer("Нет доступа к боту", show_alert=True)

        return None
