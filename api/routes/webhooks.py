import logging

from fastapi import APIRouter, Request

from bot.services.payments.crypto_bot import process_crypto_payment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/crypto-bot")
async def crypto_bot_webhook(request: Request):
    body = await request.json()
    logger.info("Crypto Bot webhook: %s", body.get("update_type"))
    ok = await process_crypto_payment(body)
    return {"ok": ok}
