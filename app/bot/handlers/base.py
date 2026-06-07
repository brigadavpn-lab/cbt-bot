import logging

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.sql import func

from app.bot.states import BroadcastState
from app.core.config import settings
from app.db.models import User
from app.db.session import AsyncSessionLocal
from app.utils.html import esc

logger = logging.getLogger(__name__)
router = Router()


# Функция рисования меню (чтобы не дублировать код)
def get_main_menu(is_admin: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(text="🏋️ Тренировка", callback_data="start_training")
    builder.button(text="🎲 ИИ-Генератор задач", callback_data="generate_new_task")
    builder.button(text="📝 Тест (10 вопросов)", callback_data="start_test")
    builder.button(text="🧠 Своя ситуация", callback_data="my_situation")
    builder.button(text="📈 Мой прогресс", callback_data="my_progress")
    if is_admin:
        builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.adjust(1)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    # Сбрасываем любые зависшие состояния (тесты, диалоги)
    await state.clear()

    tg_id = message.from_user.id

    # SELECT-then-INSERT: определяем, новый ли это пользователь
    is_new_user = False
    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.tg_id == tg_id))
        ).scalar_one_or_none()
        if existing is None:
            session.add(User(
                tg_id=tg_id,
                level=1,
                xp=0,
                streak=0,
                max_streak=0,
                full_name=message.from_user.full_name,
                last_active_at=func.now(),
            ))
            await session.commit()
            is_new_user = True
        else:
            existing.last_active_at = func.now()
            if existing.full_name != message.from_user.full_name:
                existing.full_name = message.from_user.full_name
            await session.commit()

    text = (
        f"Привет, <b>{esc(message.from_user.full_name)}</b>! 👋\n\n"
        "Я — <b>CBT-Gym</b>, твой персональный тренажер по работе с автоматическими мыслями.\n"
        "Я помогаю находить когнитивные искажения — ошибки в мыслях, которые вызывают тревогу и стресс.\n\n"
        "💪 <b>Как мы будем тренироваться?</b>\n"
        "• <b>Генератор задач:</b> Решай уникальные кейсы от ИИ.\n"
        "• <b>Своя ситуация:</b> Расскажи проблему, и я помогу её разобрать.\n"
        "• <b>Прогресс:</b> Копи опыт (XP) и следи за серией побед!\n\n"
        "С чего начнем?"
    )
    is_admin = (tg_id == settings.ADMIN_TG_ID and settings.ADMIN_TG_ID != 0)
    await message.answer(text, reply_markup=get_main_menu(is_admin=is_admin))

    # Уведомление админу о новом пользователе (если ADMIN_TG_ID задан и это не сам админ)
    if is_new_user and settings.ADMIN_TG_ID and tg_id != settings.ADMIN_TG_ID:
        try:
            await message.bot.send_message(
                chat_id=settings.ADMIN_TG_ID,
                text=(
                    "👤 <b>Новый пользователь!</b>\n\n"
                    f"Имя: {esc(message.from_user.full_name)}\n"
                    f"Username: @{esc(message.from_user.username)}\n"
                    f"ID: {tg_id}"
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Failed to notify admin about new user %s", tg_id)


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять. Вы в главном меню.")
        return
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    await message.answer("❌ Действие отменено.", reply_markup=builder.as_markup())


# УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК КНОПКИ "НАЗАД"
@router.callback_query(F.data == "back_to_menu")
async def go_home(callback: types.CallbackQuery, state: FSMContext):
    # 1. Сбрасываем состояние (если пользователь был посреди теста)
    await state.clear()

    # 2. Меняем текст на главное меню
    text = "Вы вернулись в главное меню. Чем займемся?"
    is_admin = (callback.from_user.id == settings.ADMIN_TG_ID and settings.ADMIN_TG_ID != 0)
    await callback.message.edit_text(text, reply_markup=get_main_menu(is_admin=is_admin))
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_btn(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != settings.ADMIN_TG_ID or settings.ADMIN_TG_ID == 0:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(BroadcastState.waiting_for_text)
    await callback.message.answer("✍️ Введите текст рассылки:\n\nДля отмены отправьте /cancel")
    await callback.answer()
