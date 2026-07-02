import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot.config import settings
from bot.db.session import get_session
from bot.services.access_facade import check_download_access
from bot.services.payments.crypto_bot import create_crypto_invoice
from bot.services.subscription import activate_subscription, get_plan, list_plans, record_payment
from bot.services.users import upsert_user

router = Router()
logger = logging.getLogger(__name__)


def _premium_keyboard(plans: list, crypto_links: dict[int, str]) -> InlineKeyboardMarkup:
    rows = []
    for plan in plans:
        row = [
            InlineKeyboardButton(
                text=f"⭐ {plan.name} — {plan.price_stars} Stars",
                callback_data=f"pay:stars:{plan.id}",
            )
        ]
        if plan.id in crypto_links:
            row.append(
                InlineKeyboardButton(
                    text=f"💎 {plan.price_usdt} USDT",
                    url=crypto_links[plan.id],
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _premium_text(session, user_id: int, chat_id: int) -> str:
    status = await check_download_access(session, user_id, chat_id)
    lines = ["⭐ <b>Premium</b>\n"]
    if status.reason == "premium":
        lines.append(f"✅ Активен до: <b>{status.premium_until}</b>\n")
    elif status.reason == "unlimited":
        lines.append("✅ У вас безлимитный доступ\n")
    else:
        lines.append(f"📊 Сегодня: {status.limit - status.remaining}/{status.limit} загрузок\n")
        lines.append("Premium — безлимитные загрузки.\n")
    lines.append("Выберите тариф:")
    return "\n".join(lines)


@router.message(Command("premium"))
async def cmd_premium(message: Message) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    async with get_session() as session:
        await upsert_user(
            session,
            user_id,
            message.from_user.username,
            message.from_user.first_name,
        )
        plans = await list_plans(session)
        crypto_links: dict[int, str] = {}
        for plan in plans:
            if plan.price_usdt > 0:
                invoice = await create_crypto_invoice(plan, user_id)
                if invoice:
                    crypto_links[plan.id] = invoice.get("pay_url", "")
        text = await _premium_text(session, user_id, chat_id)
    await message.answer(text, reply_markup=_premium_keyboard(plans, crypto_links))


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    async with get_session() as session:
        await upsert_user(
            session,
            user_id,
            message.from_user.username,
            message.from_user.first_name,
        )
        status = await check_download_access(session, user_id, chat_id)
    if status.reason == "premium":
        text = f"⭐ Premium активен до <b>{status.premium_until}</b>"
    elif status.reason == "unlimited":
        text = "✅ Безлимитный доступ"
    else:
        used = status.limit - status.remaining
        text = f"📊 Сегодня: <b>{used}/{status.limit}</b> загрузок"
    await message.answer(text)


@router.callback_query(F.data.startswith("pay:stars:"))
async def pay_stars(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return
    plan_id = int(callback.data.split(":")[-1])
    user_id = callback.from_user.id
    async with get_session() as session:
        plan = await get_plan(session, plan_id)
        if not plan:
            await callback.answer("Тариф не найден", show_alert=True)
            return
        payload = json.dumps({"plan_id": plan.id, "user_id": user_id})
        prices = [LabeledPrice(label=plan.name, amount=plan.price_stars)]
    await callback.message.answer_invoice(
        title=f"Premium: {plan.name}",
        description=f"Безлимитные загрузки на {plan.duration_days} дней",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    try:
        payload = json.loads(query.invoice_payload)
        plan_id = int(payload["plan_id"])
        user_id = int(payload["user_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        await query.answer(ok=False, error_message="Неверные данные платежа")
        return
    if query.from_user.id != user_id:
        await query.answer(ok=False, error_message="Платёж привязан к другому пользователю")
        return
    async with get_session() as session:
        plan = await get_plan(session, plan_id)
        if not plan or plan.price_stars != query.total_amount:
            await query.answer(ok=False, error_message="Тариф изменился, попробуйте снова")
            return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    if not message.from_user or not message.successful_payment:
        return
    payment_info = message.successful_payment
    try:
        payload = json.loads(payment_info.invoice_payload)
        plan_id = int(payload["plan_id"])
        user_id = int(payload["user_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        await message.answer("❌ Ошибка обработки платежа. Обратитесь к администратору.")
        return
    if message.from_user.id != user_id:
        await message.answer("❌ Ошибка: неверный пользователь платежа.")
        return

    external_id = f"stars:{payment_info.telegram_payment_charge_id}"
    async with get_session() as session:
        plan = await get_plan(session, plan_id)
        if not plan:
            await message.answer("❌ Тариф не найден.")
            return
        pay = await record_payment(
            session,
            user_id,
            plan,
            provider="stars",
            amount=float(payment_info.total_amount),
            currency="XTR",
            external_id=external_id,
        )
        if pay is None:
            await message.answer("✅ Premium уже активирован для этого платежа.")
            return
        sub = await activate_subscription(session, user_id, plan, source="stars", payment=pay)
        expires = sub.expires_at.strftime("%d.%m.%Y")
    await message.answer(f"✅ Premium активирован до <b>{expires}</b>!")
