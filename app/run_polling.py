import asyncio
import logging
from app.bot.dispatcher import dp
from app.main import bot

logging.basicConfig(level=logging.INFO)

async def main():
    print("🚀 Запускаем бота в режиме Polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())