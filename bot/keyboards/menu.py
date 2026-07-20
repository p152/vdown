from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def back_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]


def main_menu_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📊 Мой лимит", callback_data="menu:status"),
            InlineKeyboardButton(text="⭐ Premium", callback_data="menu:premium"),
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu:help"),
            InlineKeyboardButton(text="🐛 Поддержка", callback_data="menu:feedback"),
        ],
        [InlineKeyboardButton(text="⏹ Отменить загрузку", callback_data="menu:cancel")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def screen_keyboard(extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = list(extra_rows or [])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_keyboard(
    plan_rows: list[list[InlineKeyboardButton]],
) -> InlineKeyboardMarkup:
    rows = list(plan_rows)
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            back_row(),
        ]
    )


def paywall_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Купить Premium", callback_data="menu:premium")],
            back_row(),
        ]
    )
