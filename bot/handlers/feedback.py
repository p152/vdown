import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.menu import main_menu_keyboard
from bot.services.feedback import notify_admins, save_feedback
from bot.states.feedback import FeedbackStates

router = Router()
logger = logging.getLogger(__name__)


@router.message(FeedbackStates.waiting_message)
async def feedback_receive(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.bot:
        return

    text = (message.text or message.caption or "").strip()
    photo_file_id = None

    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if not text:
            text = "(без текста, только скриншот)"

    if not text and not photo_file_id:
        await message.answer("Отправьте текст или фото с описанием проблемы.")
        return

    await save_feedback(message.from_user, text, has_photo=bool(photo_file_id))
    await notify_admins(message.bot, message.from_user, text, photo_file_id=photo_file_id)
    await state.clear()
    await message.answer(
        "✅ Спасибо! Сообщение отправлено администратору.",
        reply_markup=main_menu_keyboard(),
    )
