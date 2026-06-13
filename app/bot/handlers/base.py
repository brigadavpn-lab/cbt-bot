import logging

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete, select
from sqlalchemy.sql import func

from app.bot.states import BroadcastState
from app.core.config import settings
from app.db.models import Attempt, TokenUsage, User
from app.db.session import AsyncSessionLocal
from app.utils.html import esc

logger = logging.getLogger(__name__)
router = Router()

WELCOME_TEXT = (
    "<b>CBT-Gym — тренажер для работы с автоматическими мыслями</b>\n\n"
    "Привет, <b>{name}</b>! 👋\n\n"
    "Ты замечал, что одна и та же ситуация вызывает у людей совершенно разные эмоции? "
    "Все зависит от того, как мы интерпретируем происходящее, и иногда наш мозг незаметно нас подводит: "
    "преувеличивает угрозы, делает поспешные выводы, видит все в черно-белом цвете. "
    "Из-за этого мы можем тревожиться, злиться или расстраивается, вообщем реагировать несоразмерно истинному положению дел.\n\n"
    "Хорошая новость: этому можно научиться противостоять. "
    "CBT-Gym — бот, который помогает тренировать именно этот навык, распознавая автоматические мысли и когнитивные искажения в них\n\n"
    "<b>Что можно делать в боте:</b>\n\n"
    "🏋️ <b>Тренировка:</b> бот показывает ситуацию и мысль персонажа, ты угадываешь, где здесь ошибка мышления. 18 видов ловушек, ситуации из реальной жизни.\n\n"
    "🎲 <b>ИИ-генератор:</b> если хочется больше заданий, ИИ придумает новую уникальную ситуацию.\n\n"
    "🧠 <b>Разобрать свою ситуацию:</b> опиши, что тебя беспокоит. Бот найдёт ловушку мышления, объяснит почему это искажение и предложит взглянуть иначе. Твоя история нигде не сохраняется.\n\n"
    "📝 <b>Тест:</b> 10 вопросов подряд, чтобы проверить свой прогресс.\n\n"
    "📈 <b>Прогресс:</b> опыт, уровни, серии побед.\n\n"
    "Бот не заменяет работу с психологом. . Но он дает возможность выработать привычку замечать, когда твои мысли искажают реальность еще до того, как эмоции захлестнули \n\n"
    "Если есть вопросы или предложения, жми кнопку обратной связи в меню. Удачи в тренировках! 💪 \n\n"
    "\n\n👨‍💻 Автор: @psychologist_drachev_andrei"
)


# Функция рисования меню (чтобы не дублировать код)
def get_main_menu(is_admin: bool = False):
    builder = InlineKeyboardBuilder()
    builder.button(text="🏋️ Тренировка", callback_data="start_training")
    builder.button(text="🎲 ИИ-Генератор задач", callback_data="generate_new_task")
    builder.button(text="📝 Тест (10 вопросов)", callback_data="start_test")
    builder.button(text="🧠 Своя ситуация", callback_data="my_situation")
    builder.button(text="📈 Мой прогресс", callback_data="my_progress")
    builder.button(text="📝 Обратная связь", callback_data="feedback")
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
    is_age_confirmed = False
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
            is_age_confirmed = existing.is_age_confirmed

    if not is_age_confirmed:
        builder = InlineKeyboardBuilder()
        builder.button(
            text='✅ Я подтверждаю, что мне исполнилось 18 лет',
            callback_data='confirm_age',
        )
        await message.answer(
            '👋 Добро пожаловать в <b>CBT-Gym</b>!\n\n'
            'Перед началом работы необходимо подтвердить возраст.\n\n'
            'Нажимая кнопку ниже, вы подтверждаете, что вам исполнилось <b>18 лет</b>.',
            parse_mode='HTML',
            reply_markup=builder.as_markup(),
        )
        return

    is_admin = (tg_id == settings.ADMIN_TG_ID and settings.ADMIN_TG_ID != 0)
    await message.answer(
        WELCOME_TEXT.format(name=esc(message.from_user.full_name)),
        parse_mode='HTML',
        reply_markup=get_main_menu(is_admin=is_admin),
    )

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


@router.callback_query(F.data == 'confirm_age')
async def handle_age_confirmation(callback: types.CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.tg_id == tg_id)
        )).scalar_one_or_none()
        if user:
            user.is_age_confirmed = True
            await session.commit()
    await callback.message.delete()
    is_admin = (tg_id == settings.ADMIN_TG_ID and settings.ADMIN_TG_ID != 0)
    await callback.message.answer(
        WELCOME_TEXT.format(name=esc(callback.from_user.full_name)),
        parse_mode='HTML',
        reply_markup=get_main_menu(is_admin=is_admin),
    )
    await callback.answer()


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


@router.message(Command("deletedata"))
async def cmd_delete_data(message: types.Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.tg_id == tg_id))
        ).scalar_one_or_none()
        if user:
            await session.execute(delete(Attempt).where(Attempt.user_id == user.id))
            await session.execute(delete(TokenUsage).where(TokenUsage.user_id == user.id))
            user.xp = 0
            user.level = 1
            user.streak = 0
            user.max_streak = 0
            user.full_name = None
            await session.commit()
    await message.answer(
        "✅ Ваши данные удалены:\n"
        "• История ответов\n"
        "• Статистика использования AI\n"
        "• Имя и прогресс\n\n"
        "Запись о вашем аккаунте сохранена для корректной работы бота."
    )
