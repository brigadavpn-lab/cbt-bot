import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiohttp import web

from app.bot.dispatcher import dp
from app.core.config import settings
from app.core.logging import setup_logging
from app.web import create_app

logger = logging.getLogger(__name__)


COMMANDS = [
    BotCommand(command="start", description="Запуск и приветствие"),
    BotCommand(command="menu", description="Главное меню"),
    BotCommand(command="reset", description="Сбросить текущее состояние"),
    BotCommand(command="help", description="Список команд"),
]


async def _run_web(bot: Bot) -> None:
    app = create_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEB_HOST, settings.WEB_PORT)
    await site.start()
    logger.info("HTTP server listening on %s:%s", settings.WEB_HOST, settings.WEB_PORT)
    try:
        # Keep the task alive until cancelled.
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    setup_logging()
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        logger.info("Starting bot in polling mode")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_my_commands(COMMANDS)
        await asyncio.gather(
            dp.start_polling(bot),
            _run_web(bot),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
