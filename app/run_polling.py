import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.bot.dispatcher import dp
from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


COMMANDS = [
    BotCommand(command="start", description="Запуск и приветствие"),
    BotCommand(command="menu", description="Главное меню"),
    BotCommand(command="reset", description="Сбросить текущее состояние"),
    BotCommand(command="help", description="Список команд"),
]


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
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
