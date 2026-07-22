# Cookies для платформ

Некоторые сервисы требуют cookies (сессию браузера) для скачивания.

| Платформа | Когда нужны |
|-----------|-------------|
| **Instagram** | Всегда |
| **Facebook** | Всегда |
| **YouTube** | Age-restricted, приватные видео |
| Twitter, VK, Twitch | Опционально |

## Как получить cookies.txt

1. Установите расширение **Get cookies.txt LOCALLY**:
   - [Chrome](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - [Firefox](https://addons.mozilla.org/firefox/addon/cookies-txt/)
2. Войдите на сайт (youtube.com, instagram.com и т.д.)
3. Экспортируйте cookies
4. Загрузите в web-админке → **Сервисы** → нужная платформа → «Загрузить cookies»
5. Нажмите **«Синхронизировать с VidBee»**

## Альтернатива — через Telegram-бота

1. `ADMIN_IDS` в `.env`
2. Отправьте боту файл `cookies.txt` как документ

## Проверка

Статус сервисов — в web-админке → **Сервисы**.

Cookies нужно обновлять периодически (раз в несколько недель), когда сессия истекает.
