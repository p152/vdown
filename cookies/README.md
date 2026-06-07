# Instagram cookies

Instagram блокирует скачивание с серверов без авторизации. Нужен файл `cookies.txt` в формате Netscape.

## Как получить cookies.txt

1. Установите расширение браузера **Get cookies.txt LOCALLY**:
   - [Chrome](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - [Firefox](https://addons.mozilla.org/firefox/addon/cookies-txt/)
2. Откройте [instagram.com](https://www.instagram.com) и войдите в аккаунт
3. Экспортируйте cookies (домен `.instagram.com`)
4. Сохраните как `cookies/cookies.txt` в этом проекте

## Способ 1 — файл на сервере

```bash
cp ~/Downloads/cookies.txt cookies/cookies.txt
docker compose restart bot worker vidbee-api
```

## Способ 2 — через Telegram-бота

1. Добавьте свой Telegram ID в `.env`:
   ```
   ADMIN_IDS=123456789
   ```
2. Перезапустите бота: `docker compose restart bot`
3. Отправьте боту файл `cookies.txt` как документ

## Проверка

В боте: `/cookies_status`

Cookies нужно обновлять периодически (раз в несколько недель), когда Instagram разлогинивает сессию.
