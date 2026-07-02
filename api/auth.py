import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from jose import JWTError, jwt
from pydantic import BaseModel

from bot.config import admin_id_set, settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


class TelegramAuthData(BaseModel):
    id: int
    first_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class PasswordAuth(BaseModel):
    password: str


def verify_telegram_login(data: TelegramAuthData) -> bool:
    admins = admin_id_set()
    if not admins or data.id not in admins:
        return False
    check_hash = data.hash
    payload = data.model_dump(exclude={"hash"})
    data_check_arr = [f"{k}={v}" for k, v in sorted(payload.items()) if v is not None]
    data_check_string = "\n".join(data_check_arr)
    secret_key = hashlib.sha256(settings.bot_token.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, check_hash):
        return False
    if datetime.utcnow().timestamp() - data.auth_date > 86400:
        return False
    return True


def verify_password(password: str) -> bool:
    return bool(settings.admin_web_password) and password == settings.admin_web_password


def create_access_token(admin_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": str(admin_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
