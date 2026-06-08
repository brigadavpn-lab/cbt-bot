import asyncio
import logging

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.bot.states import BroadcastState
from app.core.config import settings
from app.db.models import User
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != settings.ADMIN_TG_ID:
        await message.answer("⛔ Нет доступа.")
        return
    if settings.ADMIN_TG_ID == 0:
        await message.answer("⛔ Администратор не настроен.")
        return
    await state.set_state(BroadcastState.waiting_for_text)
    await message.answer("✍️ Введите текст рассылки:\n\nДля отмены отправьте /cancel")


@router.message(BroadcastState.waiting_for_text, F.text)
async def receive_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(BroadcastState.waiting_for_photo)

    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Пропустить фото", callback_data="broadcast_skip_photo")
    builder.button(text="❌ Отмена", callback_data="broadcast_cancel")
    builder.adjust(1)
    await message.answer(
        "✍️ Прикрепите фото к рассылке или нажмите Пропустить",
        reply_markup=builder.as_markup(),
    )


@router.message(BroadcastState.waiting_for_photo, F.photo)
async def receive_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_id=file_id)
    await show_preview(message, state)


@router.callback_query(BroadcastState.waiting_for_photo, F.data == "broadcast_skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(photo_id=None)
    await show_preview(callback, state)


async def show_preview(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("text", "")
    photo_id = data.get("photo_id")

    await state.set_state(BroadcastState.confirm)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data="broadcast_confirm")
    builder.button(text="❌ Отмена", callback_data="broadcast_cancel")
    builder.adjust(1)
    markup = builder.as_markup()

    bot = event.bot
    if isinstance(event, types.Message):
        chat_id = event.chat.id
    else:
        chat_id = event.message.chat.id

    caption = f"✍️ Превью рассылки:\n\n{text}"

    if photo_id:
        await bot.send_photo(chat_id, photo=photo_id, caption=caption, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text=caption, reply_markup=markup)

    if isinstance(event, types.CallbackQuery):
        await event.answer()


@router.callback_query(BroadcastState.confirm, F.data == "broadcast_confirm")
async def confirm_broadcast(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    text = data.get("text", "")
    photo_id = data.get("photo_id")

    await state.clear()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.tg_id, User.full_name))
        users = result.all()

    await callback.message.answer("✍️ Начинаю рассылку...")
    await callback.answer()

    sent = 0
    blocked = 0    # 403 — пользователь заблокировал бота
    not_found = 0  # 400 — аккаунт удалён или чат недоступен
    failed = 0     # прочие ошибки
    for tg_id, full_name in users:
        personalized = text.replace("{name}", full_name or "Пользователь")
        try:
            if photo_id:
                await bot.send_photo(tg_id, photo=photo_id, caption=personalized)
            else:
                await bot.send_message(tg_id, text=personalized)
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
            logger.info('broadcast: user %s blocked the bot', tg_id)
        except TelegramBadRequest as e:
            not_found += 1
            logger.info('broadcast: chat not found for user %s: %s', tg_id, e.message)
        except Exception as e:
            failed += 1
            logger.error('broadcast: unexpected error for user %s: %s', tg_id, type(e).__name__)
        await asyncio.sleep(0.05)

    lines = ['✅ Рассылка завершена.\n']
    lines.append(f'📨 Отправлено: {sent}')
    if blocked:
        lines.append(f'📨 Заблокировали бота: {blocked}')
    if not_found:
        lines.append(f'📨 Аккаунт не найден: {not_found}')
    if failed:
        lines.append(f'📨 Другие ошибки: {failed}')
    total_errors = blocked + not_found + failed
    if total_errors:
        lines.append(f'\nВсего ошибок: {total_errors}')
    await callback.message.answer('\n'.join(lines))


@router.callback_query(
    StateFilter(
        BroadcastState.waiting_for_text,
        BroadcastState.waiting_for_photo,
        BroadcastState.confirm,
    ),
    F.data == "broadcast_cancel",
)
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()
