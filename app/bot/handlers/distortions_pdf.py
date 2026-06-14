import logging
import os

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile

router = Router()
logger = logging.getLogger(__name__)

PDF_PATH = 'static/distortions.pdf'


@router.callback_query(F.data == 'distortions_pdf')
async def send_distortions_pdf(callback: CallbackQuery):
    if not os.path.exists(PDF_PATH):
        logger.error('distortions_pdf: file not found at %s', PDF_PATH)
        await callback.answer('⚠️ Файл временно недоступен.', show_alert=True)
        return
    await callback.answer()
    await callback.message.answer_document(
        document=FSInputFile(PDF_PATH, filename='Когнитивные_искажения.pdf'),
        caption='⚠️ <b>Список когнитивных искажений</b>\n\nСохрани себе для удобства.',
        parse_mode='HTML',
    )
