from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.formats import FormatChoice


def format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 720p", callback_data=f"fmt:{FormatChoice.VIDEO_720}"),
                InlineKeyboardButton(text="🎬 1080p", callback_data=f"fmt:{FormatChoice.VIDEO_1080}"),
            ],
            [
                InlineKeyboardButton(text="🎵 Аудио MP3", callback_data=f"fmt:{FormatChoice.AUDIO}"),
                InlineKeyboardButton(text="⭐ Лучшее", callback_data=f"fmt:{FormatChoice.BEST}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="fmt:cancel"),
            ],
        ]
    )
