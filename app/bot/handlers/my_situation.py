import asyncio
import logging
import re
import uuid
from datetime import date

from anthropic import AsyncAnthropic
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import redis.asyncio as aioredis

from app.core.config import settings
from app.bot.states import UserState
from app.bot.constants.crisis import CRISIS_KEYWORDS, CRISIS_RESPONSE
from app.db.session import AsyncSessionLocal
from app.db.models import User
from app.utils.html import esc

logger = logging.getLogger(__name__)
router = Router()

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY.get_secret_value())

SITUATION_SYSTEM_PROMPT = """
Ты — опытный психолог, специалист по когнитивно-поведенческой терапии (КПТ).
Твоя задача — проанализировать ситуацию пользователя и помочь выявить когнитивные искажения.

Используй ТОЛЬКО термины из этого списка:
1. Черно-белое мышление
2. Чтение мыслей
3. Сверхобобщение
4. Катастрофизация
5. Предсказания будущего
6. Обесценивание
7. Негативный фильтр
8. Завышенные стандарты
9. Тирания долженствования
10. Магическое мышление
11. Навешивание ярлыков
12. Персонализация
13. Обвинение
14. Неадекватные социальные сравнения
15. Ориентация на сожаление
16. Эффект невозвратных затрат
17. Ретроспективное искажение
18. Эмоциональное обоснование

Формат ответа строго:
1. 🧐 Когнитивное искажение: [название из списка]
2. 🧠 Почему это ошибка: [краткое объяснение]
3. 💡 Рациональный ответ: [как стоит думать]

Не используй никакую разметку: ни Markdown, ни HTML, ни звёздочки, ни подчёркивания. Только чистый текст и уместные эмодзи.
Отвечай эмпатично, с поддержкой. Отвечай на русском языке.
""".strip()


@router.callback_query(F.data == "my_situation")
async def start_my_situation(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_for_situation)

    text = (
        "🧠 <b>Разбор вашей ситуации</b>\n\n"
        "Опишите, что случилось, и какие мысли у вас возникли.\n"
        "<i>Пример: Начальник косо посмотрел, наверное, хочет меня уволить.</i>\n\n"
        "✍️ <b>Напишите вашу ситуацию ниже:</b>\n\n"
        "<i>Чтобы отменить — напишите /cancel</i>\n\n"
        "⚠️ Текст вашей ситуации будет обработан сервисом Anthropic Claude.\n"
        "⚠️ Бот не является психологической помощью и не заменяет специалиста."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="back_to_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(UserState.waiting_for_situation)
async def process_situation(message: types.Message, state: FSMContext):
    if not settings.ANTHROPIC_API_KEY.get_secret_value():
        await message.answer("⚠️ Ошибка: AI-ключ не настроен.")
        await state.clear()
        return

    user_text = message.text

    user_text_lower = user_text.lower()
    is_crisis = any(keyword in user_text_lower for keyword in CRISIS_KEYWORDS)
    if is_crisis:
        await state.clear()
        builder = InlineKeyboardBuilder()
        builder.button(text='💙 В главное меню', callback_data='back_to_menu')
        await message.answer(
            CRISIS_RESPONSE,
            parse_mode='HTML',
            reply_markup=builder.as_markup()
        )
        logger.warning('crisis_routing: triggered for user_id=%s', message.from_user.id)
        return

    if len(user_text) > settings.MAX_SITUATION_LENGTH:
        await message.answer(
            f"⚠️ Текст слишком длинный. Максимум {settings.MAX_SITUATION_LENGTH} символов "
            f"(у вас {len(user_text)})."
        )
        await state.clear()
        return

    user_id = message.from_user.id

    if not settings.REDIS_URL:
        logger.error("AI function disabled: REDIS_URL not configured")
        await message.answer("⚠️ AI-функция временно недоступна. Попробуйте позже.")
        await state.clear()
        return

    redis_client = aioredis.from_url(settings.REDIS_URL)
    lock_key = f"ai_lock:{user_id}"
    lock_token = str(uuid.uuid4())

    try:
        acquired = await asyncio.wait_for(
            redis_client.set(lock_key, lock_token, nx=True, ex=settings.AI_LOCK_TTL),
            timeout=2.0,
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.error("Redis unavailable for AI quota: %s", type(e).__name__)
        await message.answer("⚠️ AI-функция временно недоступна. Попробуйте позже.")
        await redis_client.aclose()
        await state.clear()
        return

    if not acquired:
        await message.answer("⏳ Подождите, ваш запрос уже обрабатывается.")
        await redis_client.aclose()
        return

    quota_key = f"ai_daily:{user_id}:{date.today().isoformat()}"
    count = await redis_client.incr(quota_key)
    if count == 1:
        await redis_client.expire(quota_key, 86400)
    if count > settings.AI_DAILY_LIMIT:
        await redis_client.delete(lock_key)
        await message.answer(
            f"⚠️ Достигнут дневной лимит ({settings.AI_DAILY_LIMIT} запросов к ИИ). Попробуйте завтра."
        )
        await redis_client.aclose()
        await state.clear()
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SITUATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}]
        )
        ai_answer = response.content[0].text

        try:
            async with AsyncSessionLocal() as token_session:
                from app.db.models import TokenUsage
                from sqlalchemy import select as sa_select
                user_row = await token_session.execute(
                    sa_select(User.id).where(User.tg_id == message.from_user.id)
                )
                db_user_id = user_row.scalar_one_or_none()
                token_session.add(TokenUsage(
                    user_id=db_user_id,
                    feature="my_situation",
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                ))
                await token_session.commit()
        except Exception:
            logger.warning("Failed to log token usage for my_situation")

        # Убираем Markdown разметку, затем экранируем для HTML-режима
        ai_answer = re.sub(r'\*+', '', ai_answer)
        ai_answer = re.sub(r'_+', '', ai_answer)
        ai_answer = re.sub(r'`+', '', ai_answer)
        ai_answer = esc(ai_answer)

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Разобрать другую ситуацию", callback_data="my_situation")
        builder.button(text="🔙 В главное меню", callback_data="back_to_menu")
        builder.adjust(1)

        await message.answer(ai_answer, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(
            "Claude API failed for user_id=%s feature=my_situation error=%s",
            message.from_user.id,
            type(e).__name__,
        )
        await message.answer("⚠️ Произошла ошибка при связи с ИИ. Попробуйте позже.")
    finally:
        try:
            lua_script = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""
            await redis_client.eval(lua_script, 1, lock_key, lock_token)
            await redis_client.aclose()
        except Exception:
            pass

    await state.clear()
