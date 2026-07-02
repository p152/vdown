from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    download_logs: Mapped[list["DownloadLog"]] = relationship(back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    duration_days: Mapped[int] = mapped_column(Integer)
    price_stars: Mapped[int] = mapped_column(Integer, default=0)
    price_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("plans.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(20), default="manual")

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("plans.id"))
    provider: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10))
    external_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="payments")
    plan: Mapped["Plan"] = relationship(back_populates="payments")


class UsageDaily(Base):
    __tablename__ = "usage_daily"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_usage_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    date: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class DownloadLog(Base):
    __tablename__ = "download_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), default="unknown")
    format_choice: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="started")
    size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="download_logs")


class DailyStat(Base):
    __tablename__ = "daily_stats"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    downloads_ok: Mapped[int] = mapped_column(Integer, default=0)
    downloads_failed: Mapped[int] = mapped_column(Integer, default=0)
    users_active: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    revenue_stars: Mapped[int] = mapped_column(Integer, default=0)
    revenue_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    premium_conversions: Mapped[int] = mapped_column(Integer, default=0)
