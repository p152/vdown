# vdown

Telegram-бот для скачивания видео с YouTube, TikTok, Instagram и 1000+ сайтов.

Стек: **Python**, **aiogram 3**, **VidBee API** (yt-dlp), **local Telegram Bot API** (до 2 ГБ), **PostgreSQL**, **FastAPI**, **Docker Compose**.

## Возможности

- Скачивание видео и аудио с 1000+ сайтов (yt-dlp / VidBee)
- Авто-скачивание коротких роликов или выбор формата (720p, 1080p, MP3, лучшее качество)
- Отправка файлов до **2 ГБ** через local Bot API
- **Freemium:** бесплатный дневной лимит + Premium-подписка без лимитов
- Оплата через **Telegram Stars** и **Crypto Bot** (USDT)
- **Web-админка** с аналитикой, отчётами и управлением пользователями
- Whitelist-доступ для закрытого beta (in-bot `/admin` или web-панель)

## Требования

- Docker и Docker Compose
- Токен бота от [@BotFather](https://t.me/BotFather)
- `api_id` и `api_hash` с [my.telegram.org](https://my.telegram.org) — для local Bot API

## Быстрый старт

```bash
cp .env.example .env
```

Заполните в `.env`:

| Обязательно | Описание |
|-------------|----------|
| `BOT_TOKEN` | Токен от BotFather |
| `TELEGRAM_API_ID` | API ID с my.telegram.org |
| `TELEGRAM_API_HASH` | API Hash |
| `ADMIN_IDS` | Ваш Telegram ID (через [@userinfobot](https://t.me/userinfobot)) |
| `ADMIN_WEB_PASSWORD` | Пароль для web-админки |
| `JWT_SECRET` | Секрет для JWT (смените в production) |

```bash
docker compose up -d --build
```

Проверка логов:

```bash
docker compose logs -f bot worker api
```

Web-админка: **http://localhost:8082** (порт задаётся через `API_PORT` в `.env`)

## Использование бота

1. Откройте бота в Telegram и нажмите `/start`
2. Отправьте ссылку на видео
3. Короткие ролики (до 3 мин, ~100 МБ) скачиваются автоматически
4. Для длинных — выберите формат: 720p, 1080p, аудио или лучшее качество
5. `/cancel` — отменить текущую загрузку

### Команды

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/help` | Справка |
| `/status` | Остаток бесплатных загрузок или дата Premium |
| `/premium` | Тарифы и оплата (Stars / USDT) |
| `/cancel` | Отменить текущую загрузку |
| `/cookies` | Настройка Instagram |
| `/feedback`, `/bug` | Сообщить об ошибке |
| `/admin` | In-bot админка (только `ADMIN_IDS`) |

## Монетизация (Freemium)

| Уровень | Доступ | Лимит |
|---------|--------|-------|
| **Free** | Все пользователи | `FREE_DAILY_LIMIT` загрузок в день (по умолчанию 5) |
| **Premium** | Активная подписка | Безлимит |
| **Admin / Whitelist** | `ADMIN_IDS` и whitelist | Безлимит |

### Тарифы по умолчанию

| План | Stars | USDT (Crypto Bot) |
|------|-------|-------------------|
| 7 дней | 50 ⭐ | $1 |
| 30 дней | 150 ⭐ | $3 |
| 365 дней | 1200 ⭐ | $25 |

Тарифы редактируются в web-админке (раздел **Plans**).

### Оплата Telegram Stars

Работает из коробки — пользователь нажимает кнопку Stars в `/premium`, оплачивает в Telegram.

### Оплата Crypto Bot

1. Создайте приложение в [@CryptoBot](https://t.me/CryptoBot) → получите API token
2. Укажите `CRYPTO_BOT_TOKEN` в `.env`
3. Настройте webhook на `https://your-domain.com/api/webhooks/crypto-bot`
4. Укажите `WEB_BASE_URL` — публичный URL админки (нужен **HTTPS**)

> Для production обязателен reverse proxy (nginx/Caddy) с HTTPS — и для Crypto Bot webhook, и для Telegram Login Widget.

## Web-админка

URL: **http://localhost:8082** (порт `API_PORT`, сервис `api`)

### Вход

- **Пароль** — значение `ADMIN_WEB_PASSWORD` из `.env`
- **Telegram Login** — для пользователей из `ADMIN_IDS` (нужен HTTPS и виджет на странице)

### Разделы

| Раздел | Описание |
|--------|----------|
| **Dashboard** | KPI: пользователи, загрузки, Premium, выручка |
| **Analytics** | Графики загрузок, выручки, доменов; сегменты пользователей; системные метрики |
| **Отчёты** | Сводка по пользователям, экспорт CSV |
| **Users** | Поиск, выдача/отзыв Premium, сброс лимита |
| **Plans** | CRUD тарифов (Stars / USDT) |
| **Payments** | История платежей |
| **Settings** | `free_daily_limit`, режим обслуживания |
| **Whitelist** | Управление пользователями и группами |

API-документация: **http://localhost:8082/docs**

## Архитектура

| Сервис | Порт | Описание |
|--------|------|----------|
| `bot` | — | aiogram, polling, платежи Stars |
| `worker` | — | arq, скачивание и отправка файлов |
| `api` | 8082 (по умолчанию) | FastAPI, web-админка, Crypto Bot webhook |
| `postgres` | 5432 (internal) | Пользователи, подписки, платежи, аналитика |
| `vidbee-api` | 3100 (internal) | yt-dlp через [VidBee](https://github.com/nexmoe/vidbee) |
| `telegram-bot-api` | 8081 | local Bot API, лимит 2 ГБ |
| `redis` | — | Очередь задач, whitelist, feedback |

```
Telegram User → bot (aiogram)
                    ↓
              PostgreSQL ← api (FastAPI) ← Browser (Admin)
                    ↓
              worker (arq) → VidBee → local Bot API → User
```

## Переменные окружения

### Основные

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `BOT_TOKEN` | Токен Telegram-бота | — |
| `TELEGRAM_API_ID` | API ID (my.telegram.org) | — |
| `TELEGRAM_API_HASH` | API Hash | — |
| `ADMIN_IDS` | Telegram ID админов (через запятую) | — |
| `FEEDBACK_CHAT_ID` | Чат для баг-репортов (иначе — ADMIN_IDS) | — |

### Скачивание

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `AUTO_MAX_DURATION_SEC` | Авто-скачивание если короче (сек) | 180 |
| `AUTO_MAX_SIZE_MB` | Авто-скачивание если меньше (МБ) | 100 |
| `MAX_CONCURRENT_DOWNLOADS` | Параллельных загрузок | 3 |
| `VIDBEE_PROXY` | Прокси для VidBee (опционально) | — |
| `VIDBEE_COOKIES_PATH` | Путь к cookies.txt в контейнере | `/data/cookies/cookies.txt` |

### База данных

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `vdown_secret` |
| `DATABASE_URL` | URL подключения (asyncpg) | см. `.env.example` |

### Монетизация

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `FREE_DAILY_LIMIT` | Бесплатных загрузок в день | 5 |
| `CRYPTO_BOT_TOKEN` | API token от @CryptoBot | — |
| `WEB_BASE_URL` | Публичный URL админки (для webhook) | `http://localhost:8082` |
| `API_PORT` | Порт web-админки на хосте (внутри контейнера — 8080) | `8082` |

### Web-админка

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `JWT_SECRET` | Секрет для JWT-токенов | `change-me-in-production` |
| `ADMIN_WEB_PASSWORD` | Пароль входа в админку | — |

## Доступ и whitelist

1. Укажите свой Telegram ID в `ADMIN_IDS`
2. **In-bot:** `/admin` — добавление пользователей и групп
3. **Web:** раздел Whitelist в админке
4. После добавления первого пользователя/группы бот работает в режиме **whitelist**

В открытом режиме (whitelist пуст) доступен freemium: бесплатный лимит + Premium.

## Instagram

Instagram требует cookies. Подробная инструкция: [cookies/README.md](cookies/README.md)

1. Экспортируйте `cookies.txt` с instagram.com (расширение «Get cookies.txt LOCALLY»)
2. Положите в `cookies/cookies.txt` или отправьте боту как документ
3. Проверьте: `/cookies_status`

## Локальная разработка (без Docker)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Поднимите redis, postgres, vidbee-api и telegram-bot-api отдельно
# или: docker compose up -d redis postgres vidbee-api telegram-bot-api

set BOT_TOKEN=...
set TELEGRAM_BOT_API_URL=http://localhost:8081
set VIDBEE_API_URL=http://localhost:3100
set REDIS_URL=redis://localhost:6379/0
set DATABASE_URL=postgresql+asyncpg://vdown:vdown_secret@localhost:5432/vdown
set ADMIN_WEB_PASSWORD=secret
set JWT_SECRET=dev-secret

python -m bot.main                              # терминал 1
arq bot.services.queue.WorkerSettings           # терминал 2
uvicorn api.main:app --reload --port 8082       # терминал 3
```

## Troubleshooting

### `Bind for 127.0.0.1:8080 failed: port is already allocated`

Порт на хосте занят другим приложением или старым контейнером.

**Вариант 1 — сменить порт vdown** (рекомендуется):

```bash
# В .env:
API_PORT=8082
WEB_BASE_URL=http://localhost:8082

docker compose up -d --build
```

**Вариант 2 — освободить порт 8080:**

```bash
docker compose down
# Windows PowerShell — кто слушает порт:
netstat -ano | findstr ":8080"
# Завершить процесс по PID или остановить другой контейнер:
docker ps --format "table {{.Names}}\t{{.Ports}}"
docker stop <container_name>
```

## Ограничения

- Одна активная загрузка на пользователя
- Максимальный размер файла: 2 ГБ (local Bot API)
- Instagram требует cookies (см. [cookies/README.md](cookies/README.md))
- Telegram Stars: комиссия Telegram ~30%
- Crypto Bot webhook и Telegram Login Widget требуют HTTPS в production

## Структура проекта

```
vdown/
├── bot/              # Telegram-бот (aiogram)
│   ├── handlers/     # start, download, premium, admin, ...
│   ├── services/     # vidbee, queue, subscription, payments, ...
│   └── db/           # SQLAlchemy модели
├── api/              # FastAPI admin API
├── admin-ui/         # Web-панель (статика)
├── cookies/          # Instagram cookies
├── docker-compose.yml
└── .env.example
```

## Лицензия

MIT
