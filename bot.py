"""Telegram-бот «Сценарист Reels» на Perplexity Agent API.

Запуск: python bot.py  (настройки — в файле .env, см. .env.example)
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

from perplexity_client import PerplexityClient, PerplexityError
from utils import split_message

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("reels-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PPLX_API_KEY = os.getenv("PPLX_API_KEY", "")
MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-5")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8000"))
TEMPERATURE = os.getenv("TEMPERATURE", "").strip()
TEMPERATURE = float(TEMPERATURE) if TEMPERATURE else None  # пусто — не отправлять (Anthropic не принимает)
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "true").lower() in ("1", "true", "yes")
MAX_STEPS = int(os.getenv("MAX_STEPS", "3"))
# Сколько последних сообщений диалога отправлять модели
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "24"))

# На хостингах (Render и др.) порт задаётся переменной PORT,
# локально можно задать HEALTHCHECK_PORT, по умолчанию 8080.
HEALTHCHECK_PORT = int(os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080")))

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (BASE_DIR / "prompts" / "system_prompt.txt").read_text(
    encoding="utf-8"
)

WELCOME = (
    "Привет! Я твой сценарист вирусных Reels 🔥\n\n"
    "Работаем так:\n"
    "1. Я задаю 8 вопросов о твоём ролике\n"
    "2. Ты отвечаешь развёрнуто — одним или несколькими сообщениями подряд\n"
    "3. Когда закончишь — отправляешь /done\n"
    "4. Я выдаю готовый сценарий: хук, развитие, усиление, финал с CTA, "
    "подписи, разбор почему это работает и альтернативные заходы\n\n"
    "После сценария можно писать пожелания прямо в чат — я доработаю. "
    "Новый ролик — команда /new"
)

ANKETA = (
    "👉 Чем подробнее ты ответишь — тем сильнее и точнее получится сценарий. "
    "Не пиши коротко. Пиши как будто объясняешь человеку в переписке.\n\n"
    "Пример — как отвечать правильно:\n\n"
    "❌ ПЛОХО:\n"
    "— ниша: маркетинг\n"
    "— аудитория: женщины\n\n"
    "✅ ХОРОШО:\n"
    "Ниша: я обучаю заработку через блог и Reels для новичков, которые хотят "
    "начать с нуля без вложений\n"
    "Аудитория: женщины 18–45 лет, чаще всего мамы, офисные сотрудники или "
    "девушки в декрете, которые хотят дополнительный доход, но не понимают, "
    "с чего начать и боятся, что у них не получится\n\n"
    "💡 Чем больше деталей — тем точнее сценарий и выше шанс, что ролик зайдёт.\n\n"
    "Теперь ответь на 8 вопросов:\n\n"
    "1. 🎯 ТЕМА / НИША РОЛИКА — о чём ролик и в каком контексте\n"
    "2. 👥 ЦЕЛЕВАЯ АУДИТОРИЯ — кто эти люди, их проблемы, страхи, желания\n"
    "3. 🎯 ЦЕЛЬ РОЛИКА — что должно произойти после просмотра (подписка, "
    "заявки, доверие, переход в Telegram и т.д.)\n"
    "4. 💼 ЧТО ПРОДВИГАЕТСЯ — продукт, услуга, личный блог, идея, система\n"
    "5. 💡 ГЛАВНАЯ МЫСЛЬ — одной фразой: что человек должен понять после ролика\n"
    "6. 🎤 СТИЛЬ ПОДАЧИ — спокойно / дерзко / экспертно / по-дружески / уверенно\n"
    "7. 🎬 ФОРМАТ — говорящая голова / сторителлинг / мнение / разбор / "
    "живое объяснение\n"
    "8. ⏱️ ДЛИНА РОЛИКА — 1–2 минуты, короткий / средний / длинный формат\n\n"
    "Ответы можно присылать одним сообщением или по частям — я всё запомню. "
    "Когда ответишь на всё, отправь /done — и я начну писать сценарий."
)

HELP_TEXT = (
    "Как со мной работать:\n\n"
    "• /start — начать с нуля и получить анкету из 8 вопросов\n"
    "• /new — новый сценарий (сбрасывает прошлый диалог)\n"
    "• /done — «я ответил на всё, пиши сценарий» (после ответов на анкету)\n"
    "• Ответы на анкету можно присылать одним сообщением или по частям — "
    "я их запоминаю и жду команду /done\n"
    "• После готового сценария пиши пожелания прямо в чат: «сделай хук "
    "жёстче», «перепиши под другой формат» — я помню контекст\n\n"
    "Главное правило: чем больше деталей о нише и аудитории — тем сильнее сценарий."
)

ABOUT_TEXT = (
    "🤖 Я — бот-сценарист вирусных Reels.\n\n"
    "Внутри меня работает модель Perplexity API по авторской методичке "
    "экспертного сценариста: сбор информации через 8 вопросов, анализ, "
    "сценарий по блокам с сильным хуком, советы по съёмке, варианты подписи, "
    "разбор алгоритмов Instagram и альтернативные заходы.\n\n"
    f"Текущая модель: {MODEL}\n"
    "Полный список команд: /help"
)

# Состояние диалога каждого пользователя — в памяти.
# После перезапуска бота история сбрасывается.
# mode: "anketa" — собираем ответы до команды /done,
#       "chat" — свободный режим доработки сценария.
dialogs: dict[int, dict] = {}


def new_dialog() -> dict:
    return {"mode": "anketa", "buffer": [], "history": []}


def get_client() -> PerplexityClient:
    return PerplexityClient(
        api_key=PPLX_API_KEY,
        model=MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        enable_web_search=ENABLE_WEB_SEARCH,
        max_steps=MAX_STEPS,
    )


async def send_long(message: Message, text: str) -> None:
    """Отправляет текст любой длины, разбивая на части."""
    for part in split_message(text):
        await message.answer(part)


async def generate_reply(message: Message, dialog: dict) -> None:
    """Отправляет историю в Perplexity и присылает ответ пользователю.

    Ответ модели добавляется в историю, чтобы сценарий можно было
    дорабатывать следующими сообщениями.
    """
    status = await message.answer(
        "✍️ Пишу сценарий. Это может занять 1–3 минуты — не уходи из чата."
    )
    try:
        reply_text = await asyncio.to_thread(
            get_client().chat,
            SYSTEM_PROMPT,
            dialog["history"][-HISTORY_LIMIT:],
        )
    except PerplexityError as exc:
        logger.warning(
            "Perplexity error for user %s: %s", message.from_user.id, exc.message
        )
        await status.edit_text(f"⚠️ {exc.message}")
        return
    except Exception:
        logger.exception("Неожиданная ошибка при генерации")
        await status.edit_text(
            "⚠️ Что-то пошло не так на моей стороне. Попробуй отправить сообщение ещё раз."
        )
        return

    try:
        await status.delete()
    except Exception:
        pass
    await send_long(message, reply_text)
    dialog["history"].append({"role": "assistant", "content": reply_text})
    dialog["mode"] = "chat"


# ---------- Хендлеры ----------


async def cmd_start(message: Message) -> None:
    dialogs[message.from_user.id] = new_dialog()
    await message.answer(WELCOME)
    for part in split_message(ANKETA):
        await message.answer(part)


async def cmd_new(message: Message) -> None:
    dialogs[message.from_user.id] = new_dialog()
    await message.answer("Отлично, начинаем новый сценарий 🎬")
    for part in split_message(ANKETA):
        await message.answer(part)


async def cmd_done(message: Message) -> None:
    dialog = dialogs.setdefault(message.from_user.id, new_dialog())

    if dialog["mode"] == "chat":
        await message.answer(
            "Мы уже работаем над сценарием. Просто напиши пожелание в чат — "
            "я доработаю. Начать новый сценарий: /new"
        )
        return

    if not dialog["buffer"]:
        await message.answer(
            "Пока нечего отправлять — сначала ответь на 8 вопросов из анкеты. "
            "Анкета: /start"
        )
        return

    answers = "\n\n".join(dialog["buffer"])
    dialog["history"].append({"role": "user", "content": answers})
    dialog["buffer"].clear()
    await generate_reply(message, dialog)


async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


async def cmd_about(message: Message) -> None:
    await message.answer(ABOUT_TEXT)


async def handle_text(message: Message) -> None:
    if not message.text:
        return
    dialog = dialogs.setdefault(message.from_user.id, new_dialog())

    if dialog["mode"] == "anketa":
        # Собираем ответы на анкету — сценарий пишем только по команде /done
        dialog["buffer"].append(message.text)
        count = len(dialog["buffer"])
        await message.answer(
            f"✅ Записал ({count}). Можно продолжать. "
            "Когда ответишь на все вопросы — отправь /done"
        )
        return

    dialog["history"].append({"role": "user", "content": message.text})
    await generate_reply(message, dialog)


def build_dispatcher(bot: Bot) -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_new, Command("new"))
    dp.message.register(cmd_done, Command("done"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_about, Command("about"))
    dp.message.register(handle_text, F.text)
    return dp


async def run_healthcheck() -> None:
    """Простой HTTP-эндпоинт для проверки, что бот жив.

    Отвечает "ok" на любой запрос. Нужен для мониторинга и деплоя.
    """

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(1024)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "0.0.0.0", HEALTHCHECK_PORT)
    logger.info("Healthcheck-порт: %s", HEALTHCHECK_PORT)
    async with server:
        await server.serve_forever()


async def run_keepalive() -> None:
    """Не даём бесплатному хостингу (Render) усыпить бота.

    Render усыпляет бесплатный сервис через 15 минут без входящих
    HTTP-запросов. Раз в 10 минут бот сам пингует свой публичный адрес
    (Render сам подставляет его в переменную RENDER_EXTERNAL_URL),
    поэтому сервис постоянно «активен» и работает круглосуточно.
    """
    url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if not url:
        return
    ping_url = url if url.endswith("/") else url + "/"
    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            try:
                await client.get(ping_url)
                logger.debug("Keepalive: %s", ping_url)
            except Exception:
                logger.debug("Keepalive: ping не прошёл, попробую позже")
            await asyncio.sleep(600)


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ Не задан BOT_TOKEN. Создайте бота у @BotFather, "
            "скопируйте .env.example в .env и вставьте токен."
        )
    if not PPLX_API_KEY:
        raise SystemExit(
            "❌ Не задан PPLX_API_KEY. Получите ключ на https://www.perplexity.ai/settings/api "
            "и впишите его в файл .env."
        )

    bot = Bot(token=BOT_TOKEN)
    dp = build_dispatcher(bot)

    healthcheck_task = asyncio.create_task(run_healthcheck())
    keepalive_task = asyncio.create_task(run_keepalive())

    logger.info("Бот запущен. Модель: %s", MODEL)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        healthcheck_task.cancel()
        keepalive_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
