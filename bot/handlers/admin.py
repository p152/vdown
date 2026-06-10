import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MessageOriginUser, User

from bot.access import is_admin
from bot.keyboards.admin import admin_menu_keyboard, groups_list_keyboard, users_list_keyboard
from bot.services.access_store import (
    add_group,
    add_user,
    is_whitelist_active,
    list_groups,
    list_users,
    remove_group,
    remove_user,
)
from bot.services.feedback import list_feedback
from bot.states.admin import AdminStates

router = Router()
logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"-?\d+")


def _user_is_admin(user: User) -> bool:
    return is_admin(user.id)


def _admin_only(message: Message) -> bool:
    return bool(message.from_user and is_admin(message.from_user.id))


@router.message(Command("admin"), F.func(_admin_only))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    whitelist = await is_whitelist_active()
    users = await list_users()
    groups = await list_groups()

    mode = "whitelist" if whitelist else "открытый"
    text = (
        "⚙️ <b>Админ-панель</b>\n\n"
        f"Режим: <b>{mode}</b>\n"
        f"Пользователей: {len(users)}\n"
        f"Групп: {len(groups)}\n\n"
        "Добавьте пользователя или группу — после этого бот будет доступен "
        "только им (и админам из ADMIN_IDS)."
    )
    await message.answer(text, reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "admin:menu", F.from_user.func(_user_is_admin))
async def admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not callback.message:
        await callback.answer()
        return

    whitelist = await is_whitelist_active()
    users = await list_users()
    groups = await list_groups()
    mode = "whitelist" if whitelist else "открытый"

    text = (
        "⚙️ <b>Админ-панель</b>\n\n"
        f"Режим: <b>{mode}</b>\n"
        f"Пользователей: {len(users)}\n"
        f"Групп: {len(groups)}"
    )
    await callback.message.edit_text(text, reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:users", F.from_user.func(_user_is_admin))
async def admin_users(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return

    users = await list_users()
    if not users:
        text = "👤 <b>Разрешённые пользователи</b>\n\nСписок пуст."
    else:
        lines = "\n".join(f"• <code>{user_id}</code>" for user_id in users)
        text = f"👤 <b>Разрешённые пользователи</b>\n\n{lines}\n\nНажмите ❌ чтобы удалить."
    await callback.message.edit_text(text, reply_markup=users_list_keyboard(users))
    await callback.answer()


@router.callback_query(F.data == "admin:groups", F.from_user.func(_user_is_admin))
async def admin_groups(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return

    groups = await list_groups()
    if not groups:
        text = "👥 <b>Разрешённые группы</b>\n\nСписок пуст."
    else:
        lines = "\n".join(f"• <code>{group_id}</code>" for group_id in groups)
        text = f"👥 <b>Разрешённые группы</b>\n\n{lines}\n\nНажмите ❌ чтобы удалить."
    await callback.message.edit_text(text, reply_markup=groups_list_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data == "admin:add_user", F.from_user.func(_user_is_admin))
async def admin_add_user_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return

    await state.set_state(AdminStates.waiting_user_id)
    await callback.message.edit_text(
        "➕ <b>Добавить пользователя</b>\n\n"
        "Отправьте Telegram ID (число) или перешлите сообщение от пользователя.\n\n"
        "/cancel — отмена"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add_group", F.from_user.func(_user_is_admin))
async def admin_add_group_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        await callback.answer()
        return

    chat = callback.message.chat
    if chat.type in ("group", "supergroup"):
        added = await add_group(chat.id)
        if added:
            await callback.message.edit_text(
                f"✅ Группа <code>{chat.id}</code> добавлена.",
                reply_markup=admin_menu_keyboard(),
            )
        else:
            await callback.message.edit_text(
                f"ℹ️ Группа <code>{chat.id}</code> уже в списке.",
                reply_markup=admin_menu_keyboard(),
            )
        await callback.answer()
        return

    await state.set_state(AdminStates.waiting_group_id)
    await callback.message.edit_text(
        "➕ <b>Добавить группу</b>\n\n"
        "Отправьте ID группы (отрицательное число, например <code>-1001234567890</code>)\n"
        "или добавьте бота в группу и нажмите эту кнопку там.\n\n"
        "/cancel — отмена"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:rm_user:"), F.from_user.func(_user_is_admin))
async def admin_remove_user(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        await callback.answer()
        return

    user_id = int(callback.data.removeprefix("admin:rm_user:"))
    removed = await remove_user(user_id)
    users = await list_users()

    if removed:
        text = f"✅ Пользователь <code>{user_id}</code> удалён."
    else:
        text = f"ℹ️ Пользователь <code>{user_id}</code> не найден."

    if users:
        lines = "\n".join(f"• <code>{uid}</code>" for uid in users)
        text += f"\n\n👤 Осталось:\n{lines}"

    await callback.message.edit_text(text, reply_markup=users_list_keyboard(users))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:rm_group:"), F.from_user.func(_user_is_admin))
async def admin_remove_group(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        await callback.answer()
        return

    group_id = int(callback.data.removeprefix("admin:rm_group:"))
    removed = await remove_group(group_id)
    groups = await list_groups()

    if removed:
        text = f"✅ Группа <code>{group_id}</code> удалена."
    else:
        text = f"ℹ️ Группа <code>{group_id}</code> не найдена."

    if groups:
        lines = "\n".join(f"• <code>{gid}</code>" for gid in groups)
        text += f"\n\n👥 Осталось:\n{lines}"

    await callback.message.edit_text(text, reply_markup=groups_list_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data == "admin:feedback", F.from_user.func(_user_is_admin))
async def admin_feedback_list(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer()
        return

    items = await list_feedback(limit=10)
    if not items:
        text = "📋 <b>Обратная связь</b>\n\nСообщений пока нет."
    else:
        blocks: list[str] = []
        for item in items:
            name = item.get("name") or "—"
            username = item.get("username")
            user_line = f"@{username}" if username else name
            user_id = item.get("user_id", "?")
            created = (item.get("created_at") or "")[:16].replace("T", " ")
            body = item.get("text", "")
            photo = " 📷" if item.get("has_photo") else ""
            blocks.append(f"<b>{created}</b> · {user_line} (<code>{user_id}</code>){photo}\n{body}")
        text = "📋 <b>Обратная связь</b> (последние 10)\n\n" + "\n\n—\n\n".join(blocks)

    await callback.message.edit_text(text, reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_user_id, F.from_user.func(_user_is_admin))
async def admin_receive_user_id(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    user_id: int | None = None

    if message.forward_from:
        user_id = message.forward_from.id
    elif isinstance(message.forward_origin, MessageOriginUser):
        user_id = message.forward_origin.sender_user.id
    elif message.text:
        match = ID_PATTERN.search(message.text.strip())
        if match:
            user_id = int(match.group())

    if user_id is None:
        await message.answer(
            "Не удалось определить ID. Отправьте число или перешлите сообщение пользователя."
        )
        return

    added = await add_user(user_id)
    await state.clear()

    if added:
        await message.answer(
            f"✅ Пользователь <code>{user_id}</code> добавлен.",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"ℹ️ Пользователь <code>{user_id}</code> уже в списке.",
            reply_markup=admin_menu_keyboard(),
        )


@router.message(AdminStates.waiting_group_id, F.from_user.func(_user_is_admin))
async def admin_receive_group_id(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu_keyboard())
        return

    if not message.text:
        await message.answer("Отправьте ID группы числом.")
        return

    match = ID_PATTERN.search(message.text.strip())
    if not match:
        await message.answer("Неверный формат. Пример: <code>-1001234567890</code>")
        return

    group_id = int(match.group())
    if group_id >= 0:
        await message.answer("ID группы должен быть отрицательным числом.")
        return

    added = await add_group(group_id)
    await state.clear()

    if added:
        await message.answer(
            f"✅ Группа <code>{group_id}</code> добавлена.",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"ℹ️ Группа <code>{group_id}</code> уже в списке.",
            reply_markup=admin_menu_keyboard(),
        )
