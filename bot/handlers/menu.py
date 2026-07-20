import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.access import is_admin
from bot.config import settings
from bot.db.session import get_session
from bot.keyboards.menu import feedback_keyboard, main_menu_keyboard, screen_keyboard
from bot.services.access_facade import check_download_access
from bot.services.users import upsert_user
from bot.states.feedback import FeedbackStates

router = Router()
logger = logging.getLogger(__name__)


def main_menu_text() -> str:
    return (
        "👋 <b>vdown</b> — скачивание видео\n\n"
        "Отправьте ссылку на YouTube, TikTok, Instagram, Twitter/X "
        "и 1000+ других сайтов.\n\n"
        "Короткие ролики скачиваются сразу, для длинных — выбор формата.\n\n"
        f"🆓 Бесплатно: <b>{settings.free_daily_limit}</b> загрузок в день\n"
        "⭐ Premium — безлимит\n\n"
        "Выберите действие:"
    )


HELP_TEXT = (
    "<b>Как пользоваться</b>\n\n"
    "1️⃣ Отправьте ссылку на видео\n"
    "2️⃣ Дождитесь загрузки или выберите формат\n"
    "3️⃣ Получите файл в чат\n\n"
    "<b>Сервисы</b>\n"
    "YouTube · TikTok · Instagram · Twitter/X · VK · Reddit и др.\n\n"
    "<b>Лимиты</b>\n"
    "• Бесплатно — несколько загрузок в день\n"
    "• Premium — безлимит\n"
    "• Макс. размер файла — 2 ГБ\n"
    "• Одна активная загрузка"
)

FEEDBACK_PROMPT = (
    "🐛 <b>Поддержка</b>\n\n"
    "Опишите проблему или приложите скриншот.\n"
    "Нажмите «Назад» для отмены."
)


async def _status_text(user_id: int, chat_id: int) -> str:
    async with get_session() as session:
        status = await check_download_access(session, user_id, chat_id)
    if status.reason == "premium":
        return f"⭐ <b>Premium</b>\n\nАктивен до: <b>{status.premium_until}</b>"
    if status.reason == "unlimited":
        return "✅ <b>Безлимитный доступ</b>"
    used = status.limit - status.remaining
    return (
        f"📊 <b>Ваш лимит</b>\n\n"
        f"Сегодня: <b>{used}/{status.limit}</b> загрузок\n"
        f"Осталось: <b>{status.remaining}</b>"
    )


async def _render_main(target: Message | CallbackQuery) -> None:
    admin = bool(target.from_user and is_admin(target.from_user.id))
    text = main_menu_text()
    markup = main_menu_keyboard(is_admin=admin)
    if isinstance(target, CallbackQuery):
        if not target.message:
            await target.answer()
            return
        try:
            await target.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await target.message.answer(text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user:
        async with get_session() as session:
            await upsert_user(
                session,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
            )
    await _render_main(message)


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _render_main(callback)


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return
    try:
        await callback.message.edit_text(HELP_TEXT, reply_markup=screen_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(HELP_TEXT, reply_markup=screen_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:status")
async def menu_status(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return
    text = await _status_text(callback.from_user.id, callback.message.chat.id)
    try:
        await callback.message.edit_text(text, reply_markup=screen_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=screen_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:feedback")
async def menu_feedback(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return
    await state.set_state(FeedbackStates.waiting_message)
    try:
        await callback.message.edit_text(FEEDBACK_PROMPT, reply_markup=feedback_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(FEEDBACK_PROMPT, reply_markup=feedback_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:cancel")
async def menu_cancel_download(callback: CallbackQuery) -> None:
    from bot.services.download_control import cancel_active_download

    if not callback.from_user or not callback.message:
        await callback.answer()
        return
    result = await cancel_active_download(callback.from_user.id)
    admin = is_admin(callback.from_user.id)
    try:
        await callback.message.edit_text(
            result,
            reply_markup=main_menu_keyboard(is_admin=admin),
        )
    except TelegramBadRequest:
        await callback.message.answer(result, reply_markup=main_menu_keyboard(is_admin=admin))
    await callback.answer()
