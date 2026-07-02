import json
import logging
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Plan
from bot.db.session import get_session
from bot.services.subscription import activate_subscription, get_plan, record_payment
from bot.services.users import upsert_user

logger = logging.getLogger(__name__)

CRYPTO_BOT_API = "https://pay.crypt.bot/api"


async def create_crypto_invoice(plan: Plan, user_id: int) -> dict | None:
    if not settings.crypto_bot_token:
        return None
    payload = json.dumps({"plan_id": plan.id, "user_id": user_id})
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{CRYPTO_BOT_API}/createInvoice",
            headers={"Crypto-Pay-API-Token": settings.crypto_bot_token},
            json={
                "asset": "USDT",
                "amount": str(plan.price_usdt),
                "description": f"Premium {plan.name}",
                "payload": payload,
                "paid_btn_name": "openBot",
                "paid_btn_url": f"https://t.me/{settings.web_base_url}",
                "expires_in": 3600,
            },
        )
        data = response.json()
        if not data.get("ok"):
            logger.error("Crypto Bot createInvoice failed: %s", data)
            return None
        return data["result"]


async def process_crypto_payment(update: dict) -> bool:
    if update.get("update_type") != "invoice_paid":
        return False
    invoice = update.get("payload", {})
    external_id = str(invoice.get("invoice_id", ""))
    if not external_id:
        return False
    payload_raw = invoice.get("payload") or "{}"
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        logger.warning("Invalid crypto payload: %s", payload_raw)
        return False
    plan_id = payload.get("plan_id")
    user_id = payload.get("user_id")
    if not plan_id or not user_id:
        return False

    async with get_session() as session:
        plan = await get_plan(session, int(plan_id))
        if not plan:
            return False
        payment = await record_payment(
            session,
            int(user_id),
            plan,
            provider="crypto",
            amount=float(invoice.get("amount", plan.price_usdt)),
            currency=invoice.get("asset", "USDT"),
            external_id=f"crypto:{external_id}",
        )
        if payment is None:
            return True
        await upsert_user(session, int(user_id))
        await activate_subscription(session, int(user_id), plan, source="crypto", payment=payment)
    return True
