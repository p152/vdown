# vdown

Telegram-бот для скачивания видео с YouTube, TikTok, Instagram и 1000+ сайтов.

Стек: **Python**, **aiogram 3**, **VidBee API** (yt-dlp), **local Telegram Bot API** (до 2 ГБ), **Docker Compose**.

## Требования

- Docker и Docker Compose
- Токен бота от [@BotFather](https://t.me/BotFather)
- `api_id` и `api_hash` с [my.telegram.org](https://my.telegram.org) — для local Bot API

## Быстрый старт

```bash
cp .env.example .env
# Заполните BOT_TOKEN, TELEGRAM_API_ID, TELEGRAM_API_HASH

docker compose up -d --build
```

Проверка логов:

```bash
docker compose logs -f bot worker
```

## Использование

1. Откройте бота в Telegram и нажмите `/start`
2. Отправьте ссылку на видео
3. Короткие ролики (до 3 мин, ~100 МБ) скачиваются автоматически
4. Для длинных — выберите формат: 720p, 1080p, аудио или лучшее качество
5. `/cancel` — отменить текущую загрузку

## Архитектура

| Сервис | Порт | Описание |
|--------|------|----------|
| `bot` | — | aiogram, polling |
| `worker` | — | arq, скачивание и отправка файлов |
| `vidbee-api` | 3100 (internal) | yt-dlp через [VidBee](https://github.com/nexmoe/vidbee) |
| `telegram-bot-api` | 8081 | local Bot API, лимит 2 ГБ |
| `redis` | — | очередь задач |

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `BOT_TOKEN` | Токен Telegram-бота | — |
| `TELEGRAM_API_ID` | API ID (my.telegram.org) | — |
| `TELEGRAM_API_HASH` | API Hash | — |
| `AUTO_MAX_DURATION_SEC` | Авто-скачивание если короче (сек) | 180 |
| `AUTO_MAX_SIZE_MB` | Авто-скачивание если меньше (МБ) | 100 |
| `MAX_CONCURRENT_DOWNLOADS` | Параллельных загрузок | 3 |
| `VIDBEE_PROXY` | Прокси для VidBee (опционально) | — |
| `VIDBEE_COOKIES_PATH` | Путь к cookies.txt в контейнере | `/data/cookies/cookies.txt` |
| `ADMIN_IDS` | Telegram ID админов (cookies, /admin) | — |
| `FEEDBACK_CHAT_ID` | Чат для баг-репортов (иначе — ADMIN_IDS) | — |

## Доступ и админка

1. Укажите свой Telegram ID в `ADMIN_IDS` (узнать: [@userinfobot](https://t.me/userinfobot))
2. Отправьте боту `/admin` — панель управления доступом
3. Добавьте пользователей (ID или пересланное сообщение) и группы (ID или кнопка в группе)
4. После добавления первого пользователя/группы бот работает в режиме **whitelist**

Команды:
- `/admin` — панель (только админы)
- `/feedback` или `/bug` — сообщить об ошибке (доступно всем)

## Instagram

Instagram требует cookies. Подробная инструкция: [cookies/README.md](cookies/README.md)

1. Экспортируйте `cookies.txt` с instagram.com (расширение «Get cookies.txt LOCALLY»)
2. Положите в `cookies/cookies.txt` или отправьте боту как документ
3. Проверьте: `/cookies_status`

## Локальная разработка (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Поднимите redis, vidbee-api и telegram-bot-api отдельно
export BOT_TOKEN=...
export TELEGRAM_BOT_API_URL=http://localhost:8081
export VIDBEE_API_URL=http://localhost:3100
export REDIS_URL=redis://localhost:6379/0

python -m bot.main          # терминал 1
arq bot.services.queue.WorkerSettings  # терминал 2
```

## Ограничения

- Одна активная загрузка на пользователя
- Максимальный размер файла: 2 ГБ (local Bot API)
- Instagram требует cookies (см. [cookies/README.md](cookies/README.md))

## Лицензия

MIT
