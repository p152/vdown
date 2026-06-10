from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Пользователи", callback_data="admin:users"),
                InlineKeyboardButton(text="👥 Группы", callback_data="admin:groups"),
            ],
            [
                InlineKeyboardButton(text="➕ Пользователь", callback_data="admin:add_user"),
                InlineKeyboardButton(text="➕ Группа", callback_data="admin:add_group"),
            ],
            [
                InlineKeyboardButton(text="📋 Обратная связь", callback_data="admin:feedback"),
            ],
        ]
    )


def users_list_keyboard(user_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"❌ {user_id}", callback_data=f"admin:rm_user:{user_id}")]
        for user_id in user_ids[:20]
    ]
    rows.append([InlineKeyboardButton(text="« Назад", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def groups_list_keyboard(group_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"❌ {group_id}", callback_data=f"admin:rm_group:{group_id}")]
        for group_id in group_ids[:20]
    ]
    rows.append([InlineKeyboardButton(text="« Назад", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
